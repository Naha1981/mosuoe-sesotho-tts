from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from app.services import engine


PUNCTUATION = re.compile(r"[^\w\sÀ-ÖØ-öø-ÿ'’-]+", re.UNICODE)


def normalize(text: str) -> list[str]:
    text = text.lower().strip()
    text = PUNCTUATION.sub(" ", text)
    return text.split()


def edit_distance(reference: list[str], hypothesis: list[str]) -> tuple[int, int, int]:
    """Return substitutions, insertions, deletions using word-level Levenshtein DP."""
    rows = len(reference) + 1
    cols = len(hypothesis) + 1
    dp = [[(0, 0, 0) for _ in range(cols)] for _ in range(rows)]

    for i in range(1, rows):
        dp[i][0] = (0, 0, i)
    for j in range(1, cols):
        dp[0][j] = (0, j, 0)

    for i in range(1, rows):
        for j in range(1, cols):
            if reference[i - 1] == hypothesis[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
                continue

            sub_prev = dp[i - 1][j - 1]
            ins_prev = dp[i][j - 1]
            del_prev = dp[i - 1][j]
            candidates = [
                (sub_prev[0] + 1, sub_prev[1], sub_prev[2]),
                (ins_prev[0], ins_prev[1] + 1, ins_prev[2]),
                (del_prev[0], del_prev[1], del_prev[2] + 1),
            ]
            dp[i][j] = min(candidates, key=lambda item: sum(item))

    return dp[-1][-1]


def load_manifest(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"Manifest line {line_no} is not a JSON object")
        for key in ("audio", "reference", "speaker_id"):
            if not str(record.get(key, "")).strip():
                raise ValueError(f"Manifest line {line_no} is missing '{key}'")
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ASR on a consented Lesotho Sesotho manifest")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/asr_report.json"),
    )
    args = parser.parse_args()

    records = load_manifest(args.manifest)
    if not records:
        raise SystemExit("Manifest contains no recordings")

    results: list[dict[str, Any]] = []
    total_sub = total_ins = total_del = total_ref = 0

    for record in records:
        audio_path = Path(record["audio"])
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio_bytes = audio_path.read_bytes()
        hypothesis_text = engine.transcribe(audio_bytes)
        reference_tokens = normalize(str(record["reference"]))
        hypothesis_tokens = normalize(hypothesis_text)
        substitutions, insertions, deletions = edit_distance(reference_tokens, hypothesis_tokens)
        reference_count = len(reference_tokens)
        wer = (
            (substitutions + insertions + deletions) / reference_count
            if reference_count
            else 0.0
        )

        total_sub += substitutions
        total_ins += insertions
        total_del += deletions
        total_ref += reference_count

        results.append(
            {
                "audio": str(audio_path),
                "speaker_id": record["speaker_id"],
                "district": record.get("district"),
                "environment": record.get("environment"),
                "phone_like": bool(record.get("phone_like", False)),
                "reference": record["reference"],
                "hypothesis": hypothesis_text,
                "substitutions": substitutions,
                "insertions": insertions,
                "deletions": deletions,
                "wer": wer,
            }
        )

    aggregate_errors = total_sub + total_ins + total_del
    aggregate_wer = aggregate_errors / total_ref if total_ref else 0.0
    report = {
        "asr_model": engine.settings.asr_model,
        "utterance_count": len(results),
        "reference_word_count": total_ref,
        "substitutions": total_sub,
        "insertions": total_ins,
        "deletions": total_del,
        "aggregate_wer": aggregate_wer,
        "results": results,
        "note": "This benchmark measures the selected model on the supplied local test set; it does not by itself establish Lesotho-specific production readiness.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Utterances: {len(results)}")
    print(f"Aggregate WER: {aggregate_wer:.2%}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
