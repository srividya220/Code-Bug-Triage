# Enable the project-local Streamlit wrapper for the current PowerShell session.
# This adds the current repository root to PATH so `streamlit run app.py` resolves.
$repoRoot = Get-Location
$env:Path = "$repoRoot;$env:Path"
Write-Host "Added repository root to PATH for this session:" -ForegroundColor Green
Write-Host "  $repoRoot" -ForegroundColor Yellow
Write-Host "Now run: streamlit run app.py" -ForegroundColor Green
