[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-p]{32}$')]
    [string]$ExtensionId
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$hostPath = [System.IO.Path]::GetFullPath(
    (Join-Path $projectRoot "dist\taskflow_native_host.exe")
)

if (-not (Test-Path -LiteralPath $hostPath -PathType Leaf)) {
    throw "Native host executable not found at '$hostPath'. Build it with PyInstaller first."
}

$manifestPath = Join-Path $PSScriptRoot "com.taskflow.native.json"
$manifest = [ordered]@{
    name = "com.taskflow.native"
    description = "TaskFlow Native Messaging Host"
    path = $hostPath
    type = "stdio"
    allowed_origins = @("chrome-extension://$ExtensionId/")
}
$manifestJson = $manifest | ConvertTo-Json -Depth 4
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($manifestPath, $manifestJson, $utf8WithoutBom)

$registryPath = "Software\Google\Chrome\NativeMessagingHosts\com.taskflow.native"
$registryKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registryPath)
if ($null -eq $registryKey) {
    throw "Could not create the current-user Chrome native messaging registry key."
}

try {
    $registryKey.SetValue(
        "",
        $manifestPath,
        [Microsoft.Win32.RegistryValueKind]::String
    )
}
finally {
    $registryKey.Dispose()
}

Write-Host "TaskFlow native messaging host registered for extension $ExtensionId."
Write-Host "Manifest: $manifestPath"
