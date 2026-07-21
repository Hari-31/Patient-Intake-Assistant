Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ======================== EDIT HERE ========================
$DoctorEmail = "Nolan@doctor.com"
$PatientEmails = @(
    
    "lewis@gmail.com"

)
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
$ServiceRoleKey = Get-DotEnvValue "SUPABASE_SERVICE_ROLE_KEY"
$adminHeaders = @{
    apikey = $ServiceRoleKey
    Authorization = "Bearer $ServiceRoleKey"
}

$allUsers = @(Get-AllSupabaseUsers -BaseUrl $SupabaseUrl -Headers $adminHeaders)
$normalizedDoctorEmail = $DoctorEmail.Trim().ToLowerInvariant()
$doctor = $allUsers |
    Where-Object { $_.email -and $_.email.ToLowerInvariant() -eq $normalizedDoctorEmail } |
    Select-Object -First 1
if (-not $doctor) {
    throw "Doctor account '$normalizedDoctorEmail' was not found."
}
if ($doctor.app_metadata.role -ne "doctor") {
    throw "'$normalizedDoctorEmail' does not have app_metadata.role=doctor."
}

$assignments = @()
foreach ($email in $PatientEmails) {
    $normalizedPatientEmail = $email.Trim().ToLowerInvariant()
    $patient = $allUsers |
        Where-Object { $_.email -and $_.email.ToLowerInvariant() -eq $normalizedPatientEmail } |
        Select-Object -First 1
    if (-not $patient) {
        throw "Patient account '$normalizedPatientEmail' was not found."
    }
    if ($patient.app_metadata.role -ne "patient") {
        throw "'$normalizedPatientEmail' does not have app_metadata.role=patient."
    }

    $assignments += @{
        patient_id = $patient.id
        doctor_id = $doctor.id
    }
}

$restHeaders = @{
    apikey = $ServiceRoleKey
    Authorization = "Bearer $ServiceRoleKey"
    Prefer = "resolution=merge-duplicates,return=representation"
}
$encodedConflict = [Uri]::EscapeDataString("patient_id,doctor_id")
$null = Invoke-RestMethod `
    -Method Post `
    -Uri "$SupabaseUrl/rest/v1/patient_doctor?on_conflict=$encodedConflict" `
    -Headers $restHeaders `
    -ContentType "application/json" `
    -Body ($assignments | ConvertTo-Json -Depth 4)

Write-Host "Assigned $($assignments.Count) patient(s) to $normalizedDoctorEmail."
foreach ($email in $PatientEmails) {
    Write-Host "- $($email.Trim().ToLowerInvariant())"
}
