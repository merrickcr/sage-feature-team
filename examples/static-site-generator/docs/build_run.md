# Running ssg manually

For ad-hoc verification outside the test suite — useful for the Tester or EpicVerifier when chasing a failure that looks environmental.

## One-time setup

```
pip install -e .
```

(Or run via `PYTHONPATH=src python -m ssg ...` without installing.)

## Build a tiny content directory

```
mkdir -p content
cat > content/hello.md <<'EOF'
---
title: Hello
date: 2026-05-24
---

Hello, world.
EOF

python -m ssg build
```

Expected output on stdout: `built 1 pages in <ms>ms`. Expected files: `dist/hello.html` and `dist/index.html`.

## Reset between manual runs

```
rm -rf dist content
```

## Idempotency check (matches the EpicVerifier gate)

```
python -m ssg build
cp -r dist /tmp/ssg_first
python -m ssg build
diff -r /tmp/ssg_first dist     # must produce no output
```

Any diff = build is non-deterministic, which violates the PRD requirement.
