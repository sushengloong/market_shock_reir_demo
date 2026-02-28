# market_shock_reir_demo Repo Setup

Initialize and publish `market_shock_reir_demo` as its own GitHub repository:

```bash
cd market_shock_reir_demo
rm -rf .git
git init
git add .
git commit -m "Initial slow market-data demo repo"
git branch -M main
git remote add origin git@github.com:<your-org>/market_shock_reir_demo.git
git push -u origin main
```

`market_shock_reir_demo` is an external target repo used by `reir` for analysis/planning/apply/bench demos.
