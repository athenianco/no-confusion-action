import argparse
from itertools import chain
import json
import os
from pathlib import Path
import re
import sys

from typing import List


def compile_regex() -> re.Pattern:
    try:
        with Path(__file__).with_name("regexp").open() as fin:
            return re.compile(fin.read())
    except FileNotFoundError:
        from confusables import confusable_characters
        chars = (
            [str(n) for n in range(10)] +
            ["!@#$%*()[]{}~-_+=`'\"\\/<>,.:;|"] +
            [chr(ord("a") + i) for i in range(26)] +
            [chr(ord("A") + i) for i in range(26)]
        )
        confusables = {
            c for c in chain.from_iterable((confusable_characters(c) or []) for c in chars)
            if len(c) == 1
        }
        confusables -= {chr(i) for i in range(128)}
        x = re.compile(f"[{''.join(confusables)}]")
        with open("regexp", "w", encoding="utf-8") as fout:
            fout.write(x.pattern)
        return x


def scan_file(path: Path, regexp: re.Pattern, excluded_patterns: List[str], reldir: str) -> bool:
    try:
        with path.open(encoding="utf-8") as fin:
            text = fin.read()
    except Exception as e:
        print(f"Warning: failed to read {path}: {type(e).__name__}: {e}", file=sys.stderr)
    if matches := list(regexp.finditer(text)):
        if excluded_patterns:
            exclude_re = re.compile(f"{'|'.join(re.escape(p) for p in excluded_patterns)}")
            exclude_window = max(len(p) for p in excluded_patterns)
        passed = []
        for match in matches:
            skip = False
            if excluded_patterns:
                offset = max(0, match.start() - exclude_window)
                locality = text[offset:match.end() + exclude_window]
                for excl_match in exclude_re.finditer(locality):
                    if (excl_match.start() + offset) <= match.start() and \
                            (excl_match.end() + offset) >= match.end():
                        skip = True
                        break
            if skip:
                continue
            passed.append((match.start(), match.group(0)))
        if (delta := len(matches) - len(passed)) > 0:
            print(f"Ignored {delta} confusing symbol{'s' if delta > 1 else ''} "
                  f"in {path.relative_to(reldir)}",
                  file=sys.stderr)
        if passed:
            print(f"Found {len(passed)} confusing symbol{'s' if len(passed) > 1 else ''} "
                  f"in {path.relative_to(reldir)}",
                  file=sys.stderr)
            for start, group in passed:
                print(f"Offset {start}: {group}", file=sys.stderr)
            return False
    return True


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include", default="[]")
    parser.add_argument("--exclude", default="[]")
    parser.add_argument("--exclude-patterns", default="{}")
    args = parser.parse_args()
    return (
        json.loads(args.include),
        json.loads(args.exclude),
        json.loads(args.exclude_patterns),
    )


def main():
    include, exclude, exclude_patterns = parse_args()
    cwd = Path(os.getenv("GITHUB_WORKSPACE", "."))
    include = set(chain.from_iterable(cwd.glob(os.path.relpath(s, cwd)) for s in include))
    exclude = set(chain.from_iterable(cwd.glob(os.path.relpath(s, cwd)) for s in exclude))
    include -= exclude
    exclude_patterns = {frozenset(cwd.glob(os.path.relpath(k, cwd))): v
                        for k, v in exclude_patterns.items()}
    include = sorted(include)
    regexp = compile_regex()
    success = True
    scanned = len(include)
    for file in sorted(include):
        exclude_patterns_in_file = []
        for k, v in exclude_patterns.items():
            if file in k:
                exclude_patterns_in_file.extend(v)
        success &= scan_file(file, regexp, exclude_patterns_in_file, str(cwd))
    print(f"Scanned {scanned} files.", file=sys.stderr)
    return int(not success)


if __name__ == "__main__":
    sys.exit(main())
