# auth_stream_reir_demo Repo Setup

Initialize and publish `auth_stream_reir_demo` as its own GitHub repository:

```bash
cd auth_stream_reir_demo
rm -rf .git
git init
git add .
git commit -m "Initial auth stream demo repo"
git branch -M main
git remote add origin git@github.com:sushengloong/auth_stream_reir_demo.git
git push -u origin main
```

`auth_stream_reir_demo` is an external target repo used by `reir` for analysis/planning/apply/bench demos.
