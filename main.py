import argparse
from itertools import chain
import json
import os
from pathlib import Path
import re
import sys


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


def scan_file(path: Path, comment: str, regexp: re.Pattern) -> bool:
    try:
        with path.open(encoding="utf-8") as fin:
            if not comment:
                text = fin.read()
            else:
                text = "".join(line for line in fin if not line.lstrip().startswith(comment))
    except Exception as e:
        print(f"Warning: failed to read {path}: {type(e).__name__}: {e}", file=sys.stderr)
    if matches := list(regexp.finditer(text)):
        print(f"Found {len(matches)} confusing symbol{'s' if len(matches) > 1 else ''} in {path}",
              file=sys.stderr)
        for match in matches:
            print(f"Offset {match.start()}: {match.group(0)}", file=sys.stderr)
        return False
    return True


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include", default="[]")
    parser.add_argument("--exclude", default="[]")
    parser.add_argument("--include-without-comments", default="{}")
    args = parser.parse_args()
    return (
        json.loads(args.include),
        json.loads(args.exclude),
        json.loads(args.include_without_comments),
    )


def main():
    include, exclude, include_without_comments = parse_args()
    cwd = Path(os.getenv("GITHUB_WORKSPACE", "."))
    include = set(chain.from_iterable(cwd.glob(os.path.relpath(s, cwd)) for s in include))
    exclude = frozenset(chain.from_iterable(cwd.glob(os.path.relpath(s, cwd)) for s in exclude))
    include -= exclude
    include_without_comments_refined = {}
    for k, v in include_without_comments.items():
        paths = frozenset(cwd.glob(os.path.relpath(k, cwd))) - exclude
        include_without_comments_refined[paths] = v
    include_without_comments = include_without_comments_refined
    include = sorted(include)
    regexp = compile_regex()
    success = True
    scanned = len(include)
    for file in sorted(include):
        success &= scan_file(file, "", regexp)
    for files, comment in include_without_comments.items():
        scanned += len(files)
        for file in sorted(files):
            success &= scan_file(file, comment, regexp)
    print(f"Scanned {scanned} files.", file=sys.stderr)
    return int(not success)


if __name__ == "__main__":
    sys.exit(main())
