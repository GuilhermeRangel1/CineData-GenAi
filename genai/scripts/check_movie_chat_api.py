"""Check everyday movie questions against a running CineData HTTP API."""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/movie_chat_regressions.json"


def check_case(endpoint: str, case: dict) -> tuple[str, ...]:
    payload = {
        "question": case["question"],
        "context": [{"question": question} for question in case.get("context", [])],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urlopen(request, timeout=55) as response:
            result = json.load(response)
    except HTTPError as exc:
        return (f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}",)
    except (OSError, URLError, ValueError) as exc:
        return (f"{type(exc).__name__}: {exc}",)

    answer = result.get("answer") or ""
    flags = re.IGNORECASE | re.DOTALL
    failures = [
        f"trecho esperado ausente: {pattern}"
        for pattern in case["include"]
        if not re.search(pattern, answer, flags)
    ]
    failures.extend(
        f"trecho indevido presente: {pattern}"
        for pattern in case.get("exclude", [])
        if re.search(pattern, answer, flags)
    )
    if case["text_only"] and result.get("rows"):
        failures.append("a resposta trouxe uma tabela inesperada")
    if count := case.get("suggestions"):
        suggestions = [line for line in answer.splitlines() if line.startswith("- ")]
        if len(suggestions) != count or len(set(suggestions)) != count:
            failures.append(f"esperava {count} sugestões distintas")
    if failures:
        failures.append(f"resposta: {' '.join(answer.split())}")
    return tuple(failures)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint", default="http://localhost:8080/genai/api/v1/questions",
    )
    parser.add_argument("--case", action="append", help="Executa somente o ID informado.")
    args = parser.parse_args()
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if args.case:
        unknown = set(args.case) - {case["id"] for case in cases}
        if unknown:
            parser.error(f"IDs não encontrados: {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case["id"] in args.case]

    failed = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = [(case["id"], pool.submit(check_case, args.endpoint, case)) for case in cases]
        for case_id, future in pending:
            failures = future.result()
            failed += bool(failures)
            print(f"{'FAIL' if failures else 'PASS'} {case_id}", flush=True)
            for failure in failures:
                print(f"  {failure}", flush=True)
    print(f"{len(cases) - failed}/{len(cases)} passaram.")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
