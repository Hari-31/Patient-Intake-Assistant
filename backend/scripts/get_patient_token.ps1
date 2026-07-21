$SupabaseUrl = "http://127.0.0.1:54321"

$AnonKey = (
    Get-Content .env |
    Where-Object { $_ -like "SUPABASE_ANON_KEY=*" }
) -replace "^SUPABASE_ANON_KEY=", ""

$login = Invoke-RestMethod `
    -Method Post `
    -Uri "$SupabaseUrl/auth/v1/token?grant_type=password" `
    -Headers @{ apikey = $AnonKey } `
    -ContentType "application/json" `
    -Body '{"email":"patient.two.20260716@example.test","password":"LocalPatient2!2026"}'
$login.access_token | Set-Clipboard