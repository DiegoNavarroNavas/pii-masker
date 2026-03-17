# Training taxonomy from the external multihead model project.
from pathlib import Path
DEFAULT_LOCAL_MULTIHEAD_MODEL = "local_models/multihead_model.pt"
DEFAULT_LOCAL_ENCODER_MODEL = "answerdotai/ModernBERT-base"

LOCAL_MULTIHEAD_TRAINING_LABELS = [
    "NONE",
    "PERSON",
    "ORG",
    "ADDRESS",
    "EMAIL",
    "PHONE",
    "USERNAME",
    "PASSWORD",
    "IP_ADDRESS",
    "IBAN",
    "CREDIT_CARD",
    "ID_NUMBER",
    "ACCOUNT_NUMBER",
    "OTHER",
]

# Runtime cache for local multihead checkpoints to avoid reloading on every call.
LOCAL_MULTIHEAD_RUNTIME_CACHE: dict[tuple[str, str], dict] = {}


def is_valid_token(offset_pair: tuple[int, int]) -> bool:
    start, end = offset_pair
    return not (start == 0 and end == 0)


def build_all_span_candidates(offsets: list[tuple[int, int]], max_span_len: int) -> list[list[int]]:
    valid_idxs = [i for i, off in enumerate(offsets) if is_valid_token(off)]
    candidates: list[list[int]] = []
    for start in valid_idxs:
        max_end = min(start + max_span_len, len(offsets))
        for end in range(start, max_end):
            if not is_valid_token(offsets[end]):
                break
            candidates.append([start, end])
    return candidates


def spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def resolve_local_multihead_checkpoint(model: str | None) -> Path:
    raw_path = (model or DEFAULT_LOCAL_MULTIHEAD_MODEL).strip()
    checkpoint_path = Path(raw_path)
    if not checkpoint_path.is_absolute():
        checkpoint_path = (Path.cwd() / checkpoint_path).resolve()
    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Local multihead checkpoint not found: {checkpoint_path}. "
            f"Set --model to the .pt path (default: {DEFAULT_LOCAL_MULTIHEAD_MODEL})."
        )
    return checkpoint_path


def load_local_multihead_runtime(
    checkpoint_path: Path,
    encoder_model: str | None = None,
) -> dict:
    """Load and cache local multihead runtime components for inference."""
    try:
        import torch
        import torch.nn as nn
        from transformers import AutoModel, AutoTokenizer
    except ImportError as e:
        raise ImportError(
            "Missing dependencies for local_multihead engine. "
            "Install torch and transformers in the current environment."
        ) from e

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    encoder_source = (
        (encoder_model or "").strip()
        or (
            checkpoint.get("config", {}).get("model_name", "").strip()
            if isinstance(checkpoint, dict) and isinstance(checkpoint.get("config"), dict)
            else ""
        )
        or (checkpoint.get("base_model", "").strip() if isinstance(checkpoint, dict) else "")
        or DEFAULT_LOCAL_ENCODER_MODEL
    )
    cache_key = (str(checkpoint_path.resolve()), encoder_source)
    cached = LOCAL_MULTIHEAD_RUNTIME_CACHE.get(cache_key)
    if cached:
        return cached

    tokenizer = AutoTokenizer.from_pretrained(encoder_source, use_fast=True)

    # Format A: legacy single-head span classifier checkpoint.
    if isinstance(checkpoint, dict) and ("classifier" in checkpoint or "label2id" in checkpoint):
        class LocalSpanClassifier(nn.Module):
            def __init__(self, model_name: str, num_labels: int, max_span_len: int = 6, dropout: float = 0.1):
                super().__init__()
                self.encoder = AutoModel.from_pretrained(model_name)
                hidden = self.encoder.config.hidden_size
                self.length_emb = nn.Embedding(max_span_len + 1, hidden)
                self.dropout = nn.Dropout(dropout)
                self.classifier = nn.Sequential(
                    nn.Linear(hidden * 4, hidden),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden, num_labels),
                )

            def forward(self, input_ids, attention_mask, candidate_spans):
                out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
                hidden = out.last_hidden_state  # [B, T, H]

                batch_reps = []
                for b in range(hidden.size(0)):
                    spans = candidate_spans[b]
                    valid_mask = spans[:, 0] >= 0
                    spans = spans[valid_mask]
                    if spans.numel() == 0:
                        continue
                    starts = spans[:, 0]
                    ends = spans[:, 1]
                    start_h = hidden[b, starts]
                    end_h = hidden[b, ends]

                    pooled = []
                    for s, e in zip(starts.tolist(), ends.tolist()):
                        pooled.append(hidden[b, s : e + 1].mean(dim=0))
                    pooled = torch.stack(pooled, dim=0)
                    lengths = (ends - starts + 1).clamp(max=self.length_emb.num_embeddings - 1)
                    len_h = self.length_emb(lengths)

                    rep = torch.cat([start_h, end_h, pooled, len_h], dim=-1)
                    batch_reps.append(rep)

                if not batch_reps:
                    return {"logits": torch.empty(0)}
                reps = torch.cat(batch_reps, dim=0)
                logits = self.classifier(self.dropout(reps))
                return {"logits": logits}

        state_dict = checkpoint["classifier"] if "classifier" in checkpoint else checkpoint
        if not isinstance(state_dict, dict):
            raise ValueError("Invalid checkpoint: classifier state_dict is missing.")

        label2id = checkpoint.get("label2id")
        if not isinstance(label2id, dict):
            label2id = {label: i for i, label in enumerate(LOCAL_MULTIHEAD_TRAINING_LABELS)}
        if "NONE" not in label2id:
            raise ValueError("Invalid checkpoint: label2id must include 'NONE'.")

        id2label = {v: k for k, v in label2id.items()}
        max_span_len = checkpoint.get("max_span_len", 6)
        if not isinstance(max_span_len, int) or max_span_len <= 0:
            max_span_len = 6

        model = LocalSpanClassifier(
            model_name=encoder_source,
            num_labels=len(label2id),
            max_span_len=max_span_len,
        )
        model.load_state_dict(state_dict, strict=True)
        model.eval()
        runtime = {
            "runtime_kind": "span_classifier",
            "model": model,
            "tokenizer": tokenizer,
            "label2id": label2id,
            "id2label": id2label,
            "max_span_len": max_span_len,
            "max_length": 512,
        }
    # Format B: multi-head checkpoint with proposal/type/sensitivity heads.
    elif isinstance(checkpoint, dict) and "model_state_dict" in checkpoint and "config" in checkpoint:
        class LocalMultiHeadPiiModel(nn.Module):
            def __init__(
                self,
                model_name: str,
                max_span_len: int,
                span_width_vocab_size: int = 64,
                dropout: float = 0.1,
            ):
                super().__init__()
                self.encoder = AutoModel.from_pretrained(model_name)
                hidden = self.encoder.config.hidden_size
                self.max_span_len = max_span_len
                self.dropout = nn.Dropout(dropout)
                self.proposal_head = nn.Linear(hidden, 3)
                self.width_emb = nn.Embedding(span_width_vocab_size, hidden // 2)
                span_dim = hidden * 3 + (hidden // 2)
                self.type_head = nn.Sequential(
                    nn.Linear(span_dim, hidden),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden, len(type_label_to_id)),
                )
                self.sensitivity_head = nn.Sequential(
                    nn.Linear(span_dim + len(type_label_to_id), hidden),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden, len(sensitivity_label_to_id)),
                )

            def _span_representations(self, hidden, candidate_spans):
                batch_reps = []
                for batch_idx in range(hidden.size(0)):
                    spans = candidate_spans[batch_idx]
                    valid_mask = spans[:, 0] >= 0
                    valid_spans = spans[valid_mask]
                    if valid_spans.numel() == 0:
                        continue
                    starts = valid_spans[:, 0]
                    ends = valid_spans[:, 1]
                    start_h = hidden[batch_idx, starts]
                    end_h = hidden[batch_idx, ends]
                    pooled = []
                    for s, e in zip(starts.tolist(), ends.tolist()):
                        pooled.append(hidden[batch_idx, s : e + 1].mean(dim=0))
                    pooled_h = torch.stack(pooled, dim=0)
                    widths = (ends - starts + 1).clamp(max=self.width_emb.num_embeddings - 1)
                    width_h = self.width_emb(widths.to(hidden.device))
                    rep = torch.cat([start_h, end_h, pooled_h, width_h], dim=-1)
                    batch_reps.append(rep)
                if not batch_reps:
                    return torch.empty(0, 1, device=hidden.device)
                return torch.cat(batch_reps, dim=0)

            def forward(self, input_ids, attention_mask, candidate_spans):
                out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
                hidden = out.last_hidden_state
                span_repr = self._span_representations(hidden, candidate_spans)
                if span_repr.numel() == 0:
                    return {"type_logits": torch.empty(0), "sensitivity_logits": torch.empty(0)}
                type_logits = self.type_head(self.dropout(span_repr))
                type_probs = torch.softmax(type_logits, dim=-1)
                sens_inputs = torch.cat([span_repr, type_probs], dim=-1)
                sensitivity_logits = self.sensitivity_head(self.dropout(sens_inputs))
                return {"type_logits": type_logits, "sensitivity_logits": sensitivity_logits}

        config = checkpoint.get("config", {})
        type_label_to_id = checkpoint.get("type_label_to_id", {})
        if not isinstance(type_label_to_id, dict) or "NONE" not in type_label_to_id:
            type_label_to_id = {label: i for i, label in enumerate(LOCAL_MULTIHEAD_TRAINING_LABELS)}
        sensitivity_label_to_id = checkpoint.get("sensitivity_label_to_id", {})
        if not isinstance(sensitivity_label_to_id, dict) or "REDACT" not in sensitivity_label_to_id:
            sensitivity_label_to_id = {"REDACT": 0, "KEEP": 1}

        max_span_len = int(config.get("max_span_len", 12))
        max_length = int(config.get("max_length", 512))
        redact_score_threshold = float(config.get("redact_score_threshold", 0.5))
        nms_iou_threshold = float(config.get("nms_iou_threshold", 0.5))
        span_width_vocab_size = int(config.get("span_width_vocab_size", 64))
        dropout = float(config.get("dropout", 0.1))

        model = LocalMultiHeadPiiModel(
            model_name=encoder_source,
            max_span_len=max_span_len,
            span_width_vocab_size=span_width_vocab_size,
            dropout=dropout,
        )
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        model.eval()
        runtime = {
            "runtime_kind": "multihead",
            "model": model,
            "tokenizer": tokenizer,
            "label2id": type_label_to_id,
            "id2label": {v: k for k, v in type_label_to_id.items()},
            "sensitivity_label_to_id": sensitivity_label_to_id,
            "max_span_len": max_span_len,
            "max_length": max_length,
            "redact_score_threshold": redact_score_threshold,
            "nms_iou_threshold": nms_iou_threshold,
        }
    else:
        raise ValueError(
            "Unsupported local checkpoint format. Expected either "
            "{classifier,label2id} or {model_state_dict,config,...}."
        )

    LOCAL_MULTIHEAD_RUNTIME_CACHE[cache_key] = runtime
    return runtime


def detect_pii_with_local_multihead(
    text: str,
    checkpoint_path: Path,
    encoder_model: str | None = None,
) -> list[dict]:
    """
    Run span-classifier inference using the external ModernBERT multihead architecture.

    The expected checkpoint format is the one saved by:
    train_modernbert_span_classifier.py (contains 'classifier', 'label2id', 'max_span_len').
    """
    runtime = load_local_multihead_runtime(
        checkpoint_path=checkpoint_path,
        encoder_model=encoder_model,
    )
    model = runtime["model"]
    tokenizer = runtime["tokenizer"]
    label2id = runtime["label2id"]
    id2label = runtime["id2label"]
    max_span_len = runtime["max_span_len"]

    try:
        import torch
    except ImportError as e:
        raise ImportError(
            "Missing dependencies for local_multihead engine. "
            "Install torch in the current environment."
        ) from e

    encoded = tokenizer(
        text,
        truncation=True,
        max_length=runtime["max_length"],
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]
    offsets = [(int(s), int(e)) for s, e in encoded["offset_mapping"][0].tolist()]

    candidate_spans = build_all_span_candidates(offsets, max_span_len=max_span_len)  # type: ignore[arg-type]
    if not candidate_spans:
        return []

    spans_tensor = torch.tensor(candidate_spans, dtype=torch.long).unsqueeze(0)

    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            candidate_spans=spans_tensor,
        )
        detections: list[dict] = []
        if runtime["runtime_kind"] == "span_classifier":
            logits = outputs["logits"]
            if logits.numel() == 0:
                return []
            probs = torch.softmax(logits, dim=-1)
            pred_ids = torch.argmax(probs, dim=-1)
            none_id = int(label2id["NONE"])
            for i, pred_id in enumerate(pred_ids.tolist()):
                if pred_id == none_id:
                    continue
                label = id2label.get(pred_id)
                if not label or label == "NONE":
                    continue
                token_start, token_end = candidate_spans[i]
                char_start = offsets[token_start][0]
                char_end = offsets[token_end][1]
                if char_end <= char_start:
                    continue
                detections.append(
                    {
                        "start": char_start,
                        "end": char_end,
                        "entity_type": label,
                        "score": float(probs[i, pred_id].item()),
                    }
                )
        else:
            type_logits = outputs["type_logits"]
            sensitivity_logits = outputs["sensitivity_logits"]
            if type_logits.numel() == 0 or sensitivity_logits.numel() == 0:
                return []
            type_probs = torch.softmax(type_logits, dim=-1)
            sensitivity_probs = torch.softmax(sensitivity_logits, dim=-1)
            redact_id = int(runtime["sensitivity_label_to_id"].get("REDACT", 0))
            none_id = int(label2id["NONE"])
            threshold = float(runtime["redact_score_threshold"])
            for i in range(type_logits.size(0)):
                pred_id = int(type_probs[i].argmax(dim=-1).item())
                sens_id = int(sensitivity_probs[i].argmax(dim=-1).item())
                if pred_id == none_id or sens_id != redact_id:
                    continue
                label = id2label.get(pred_id)
                if not label or label == "NONE":
                    continue
                token_start, token_end = candidate_spans[i]
                char_start = offsets[token_start][0]
                char_end = offsets[token_end][1]
                if char_end <= char_start:
                    continue
                type_conf = float(type_probs[i, pred_id].item())
                redact_prob = float(sensitivity_probs[i, redact_id].item())
                redact_score = type_conf * redact_prob
                if redact_score < threshold:
                    continue
                detections.append(
                    {
                        "start": char_start,
                        "end": char_end,
                        "entity_type": label,
                        "score": redact_score,
                    }
                )

    # Keep only strongest non-overlapping spans (with IoU tie-breaking for multihead).
    iou_threshold = float(runtime.get("nms_iou_threshold", 0.0))
    detections.sort(key=lambda d: (d["score"], d["end"] - d["start"]), reverse=True)
    kept: list[dict] = []
    for cand in detections:
        overlap_found = False
        for prev in kept:
            if spans_overlap(cand["start"], cand["end"], prev["start"], prev["end"]):
                overlap_found = True
                break
            inter = max(0, min(cand["end"], prev["end"]) - max(cand["start"], prev["start"]))
            if inter > 0:
                union = (cand["end"] - cand["start"]) + (prev["end"] - prev["start"]) - inter
                iou = inter / union if union > 0 else 0.0
                if iou >= iou_threshold:
                    overlap_found = True
                    break
        if overlap_found:
            continue
        kept.append(cand)

    kept.sort(key=lambda d: d["start"])
    return kept

