Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ======================== EDIT HERE ========================
$DoctorEmail = "Nolan@doctor.com"
$DoctorName = "Nolan"
$ShowToken = $false  # Change to $true to also print the bearer token.
# ===========================================================

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $ProjectRoot ".env"

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Key)

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        throw ".env was not found at $EnvPath"
    }

    $prefix = "$Key="
    $line = Get-Content -LiteralPath $EnvPath |
        Where-Object { $_.TrimStart().StartsWith($prefix) } |
        Select-Object -First 1
    if (-not $line) {
        throw "$Key is missing from .env"
    }

    $value = $line.Trim().Substring($prefix.Length).Trim()
    if (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    if (-not $value) {
        throw "$Key is empty in .env"
    }
    return $value
}

function Convert-SecureStringToPlainText {
    param([Parameter(Mandatory = $true)][Security.SecureString]$SecureValue)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Get-AllSupabaseUsers {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [Parameter(Mandatory = $true)][hashtable]$Headers
    )

    $users = @()
    $page = 1
    $perPage = 1000
    do {
        $result = Invoke-RestMethod `
            -Method Get `
            -Uri "$BaseUrl/auth/v1/admin/users?page=$page&per_page=$perPage" `
            -Headers $Headers
        $pageUsers = @($result.users)
        $users += $pageUsers
        $page += 1
    } while ($pageUsers.Count -eq $perPage)
    return $users
}

$SupabaseUrl = (Get-DotEnvValue "SUPABASE_URL").TrimEnd([char]"/")
$AnonKey = Get-DotEnvValue "SUPABASE_ANON_KEY"
$ServiceRoleKey = Get-DotEnvValue "SUPABASE_SERVICE_ROLE_KEY"

$securePassword = Read-Host "Doctor password" -AsSecureString
$Password = Convert-SecureStringToPlainText $securePassword
if ($Password.Length -lt 8) {
    throw "Doctor password must contain at least 8 characters."
}

$adminHeaders = @{
    apikey = $ServiceRoleKey
    Authorization = "Bearer $ServiceRoleKey"
}

$normalizedEmail = $DoctorEmail.Trim().ToLowerInvariant()
$existingUser = Get-AllSupabaseUsers `
    -BaseUrl $SupabaseUrl `
    -Headers $adminHeaders |
    Where-Object { $_.email -and $_.email.ToLowerInvariant() -eq $normalizedEmail } |
    Select-Object -First 1

$doctorPayload = @{
    email = $normalizedEmail
    password = $Password
    email_confirm = $true
    app_metadata = @{ role = "doctor" }
    user_metadata = @{ name = $DoctorName.Trim() }
} | ConvertTo-Json -Depth 5

if ($existingUser) {
    $doctor = Invoke-RestMethod `
        -Method Put `
        -Uri "$SupabaseUrl/auth/v1/admin/users/$($existingUser.id)" `
        -Headers $adminHeaders `
        -ContentType "application/json" `
        -Body $doctorPayload
    $action = "Updated"
}
else {
    $doctor = Invoke-RestMethod `
        -Method Post `
        -Uri "$SupabaseUrl/auth/v1/admin/users" `
        -Headers $adminHeaders `
        -ContentType "application/json" `
        -Body $doctorPayload
    $action = "Created"
}

if ($doctor.PSObject.Properties.Name -contains "user") {
    $doctor = $doctor.user
}

$loginPayload = @{
    email = $normalizedEmail
    password = $Password
} | ConvertTo-Json
$login = Invoke-RestMethod `
    -Method Post `
    -Uri "$SupabaseUrl/auth/v1/token?grant_type=password" `
    -Headers @{ apikey = $AnonKey } `
    -ContentType "application/json" `
    -Body $loginPayload

if (-not $login.access_token) {
    throw "Supabase did not return a doctor access token."
}

$login.access_token | Set-Clipboard
Write-Host "$action doctor $normalizedEmail ($($doctor.id))."
Write-Host "Bearer token copied to the clipboard."
if ($ShowToken) {
    Write-Output $login.access_token
}
