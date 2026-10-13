param(
    [string]$RepoPath = (Get-Location).Path,
    [string]$ConfigPath = "",
    [string]$GatewayUrl = "",
    [string]$GatewayToken = "",
    [string]$AgentId = "",
    [switch]$TestResponses
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Title
    Write-Host ("=" * 78)
}

function Mask-Secret {
    param([AllowNull()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "<missing>"
    }
    if ($Value.Length -le 8) {
        return ("*" * $Value.Length)
    }
    return "{0}...{1}" -f $Value.Substring(0, 4), $Value.Substring($Value.Length - 4, 4)
}

function Read-DotEnv {
    param([string]$Path)
    $result = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $result
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("#")) {
            continue
        }
        $idx = $trimmed.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }
        $key = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1).Trim()
        $result[$key] = $value
    }
    return $result
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Config file not found: $Path"
    }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-GatewayUrlFromConfig {
    param($Config)
    $gateway = $Config.gateway
    $port = if ($null -ne $gateway.port -and "$($gateway.port)".Trim()) { [string]$gateway.port } else { "18789" }
    $bind = if ($null -ne $gateway.bind -and "$($gateway.bind)".Trim()) { [string]$gateway.bind } else { "loopback" }
    $resolvedHost = if ($bind -in @("loopback", "localhost", "0.0.0.0", "::")) { "127.0.0.1" } else { $bind }
    return "http://{0}:{1}" -f $resolvedHost, $port
}

function Get-HttpResponse {
    param(
        [ValidateSet("GET", "POST")][string]$Method,
        [string]$Url,
        [hashtable]$Headers,
        [AllowNull()][string]$Body = $null
    )

    $request = [System.Net.HttpWebRequest]::Create($Url)
    $request.Method = $Method
    $request.Timeout = 30000
    $request.ReadWriteTimeout = 30000
    $request.Accept = "*/*"

    foreach ($entry in $Headers.GetEnumerator()) {
        $name = [string]$entry.Key
        $value = [string]$entry.Value
        switch -Regex ($name) {
            "^Authorization$" { $request.Headers["Authorization"] = $value; continue }
            "^Content-Type$" { continue }
            default { $request.Headers[$name] = $value; continue }
        }
    }

    if (-not [string]::IsNullOrEmpty($Body)) {
        $contentType = if ($Headers.ContainsKey("Content-Type")) { [string]$Headers["Content-Type"] } else { "application/json" }
        $request.ContentType = $contentType
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
        $request.ContentLength = $bytes.Length
        $stream = $request.GetRequestStream()
        try {
            $stream.Write($bytes, 0, $bytes.Length)
        }
        finally {
            $stream.Dispose()
        }
    }

    try {
        $response = [System.Net.HttpWebResponse]$request.GetResponse()
    }
    catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response) {
            throw
        }
        $response = [System.Net.HttpWebResponse]$_.Exception.Response
    }

    try {
        $bodyText = ""
        $stream = $response.GetResponseStream()
        if ($null -ne $stream) {
            $reader = New-Object System.IO.StreamReader($stream)
            try {
                $bodyText = $reader.ReadToEnd()
            }
            finally {
                $reader.Dispose()
            }
        }
        return [pscustomobject]@{
            StatusCode  = [int]$response.StatusCode
            Reason      = [string]$response.StatusDescription
            ContentType = [string]$response.ContentType
            Body        = $bodyText
            Headers     = $response.Headers
        }
    }
    finally {
        $response.Dispose()
    }
}

function Try-ParseJson {
    param([string]$Text)
    try {
        return ($Text | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Extract-OutputText {
    param($Payload)
    if ($null -eq $Payload) {
        return ""
    }
    if ($Payload.PSObject.Properties.Name -contains "output_text" -and $Payload.output_text) {
        return [string]$Payload.output_text
    }
    if ($Payload.PSObject.Properties.Name -notcontains "output" -or $null -eq $Payload.output) {
        return ""
    }

    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($item in $Payload.output) {
        if ($null -eq $item -or $item.PSObject.Properties.Name -notcontains "content") {
            continue
        }
        foreach ($part in $item.content) {
            if ($null -ne $part -and $part.type -eq "output_text" -and $part.text) {
                [void]$parts.Add([string]$part.text)
            }
        }
    }
    return ($parts -join "`n").Trim()
}

function Show-PortOwner {
    param([int]$Port)
    try {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen | Select-Object -First 1
        if ($null -eq $listener) {
            Write-Host "No listening process found on port $Port"
            return
        }

        Write-Host ("Listening socket: {0}:{1} pid={2}" -f $listener.LocalAddress, $listener.LocalPort, $listener.OwningProcess)
        try {
            $proc = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $listener.OwningProcess)
            if ($null -ne $proc) {
                Write-Host ("Process name : {0}" -f $proc.Name)
                Write-Host ("Executable   : {0}" -f $proc.ExecutablePath)
                Write-Host ("Command line : {0}" -f $proc.CommandLine)
            }
        }
        catch {
            Write-Host ("Failed to inspect process {0}: {1}" -f $listener.OwningProcess, $_.Exception.Message)
        }
    }
    catch {
        Write-Host ("Failed to inspect port {0}: {1}" -f $Port, $_.Exception.Message)
    }
}

$repoEnvPath = Join-Path $RepoPath ".env"
$repoEnv = Read-DotEnv -Path $repoEnvPath

$effectiveConfigPath = if ($ConfigPath) {
    $ConfigPath
}
elseif ($repoEnv.ContainsKey("OPENCLAW_CONFIG_PATH") -and $repoEnv["OPENCLAW_CONFIG_PATH"]) {
    $repoEnv["OPENCLAW_CONFIG_PATH"]
}
elseif ($env:OPENCLAW_CONFIG_PATH) {
    $env:OPENCLAW_CONFIG_PATH
}
else {
    Join-Path $env:USERPROFILE ".openclaw\openclaw.json"
}

$effectiveAgentId = if ($AgentId) {
    $AgentId
}
elseif ($repoEnv.ContainsKey("OPENCLAW_AGENT_ID") -and $repoEnv["OPENCLAW_AGENT_ID"]) {
    $repoEnv["OPENCLAW_AGENT_ID"]
}
elseif ($env:OPENCLAW_AGENT_ID) {
    $env:OPENCLAW_AGENT_ID
}
else {
    "llm-security-intel"
}

Write-Section "Environment"
Write-Host ("whoami              : {0}" -f [System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
Write-Host ("USERPROFILE         : {0}" -f $env:USERPROFILE)
Write-Host ("RepoPath            : {0}" -f $RepoPath)
Write-Host ("Repo .env exists    : {0}" -f (Test-Path -LiteralPath $repoEnvPath))
if ($repoEnv.Count -gt 0) {
    foreach ($key in @(
        "OPENCLAW_CONFIG_PATH",
        "SENTINEL_WORKSPACE_ROOT",
        "OPENCLAW_AGENT_ID",
        "OPENCLAW_GATEWAY_URL",
        "OPENCLAW_GATEWAY_TOKEN",
        "OPENCLAW_HOOKS_TOKEN"
    )) {
        if ($repoEnv.ContainsKey($key)) {
            $value = if ($key -like "*TOKEN*") { Mask-Secret $repoEnv[$key] } else { $repoEnv[$key] }
            Write-Host ("{0,-20}: {1}" -f $key, $value)
        }
    }
}

Write-Section "OpenClaw Config"
Write-Host ("ConfigPath          : {0}" -f $effectiveConfigPath)
$config = Read-JsonFile -Path $effectiveConfigPath
$agentEntry = $null
if ($null -ne $config.agents -and $null -ne $config.agents.list) {
    $agentEntry = @($config.agents.list) | Where-Object { $_.id -eq $effectiveAgentId } | Select-Object -First 1
}
$agentWorkspace = if ($null -ne $agentEntry -and $agentEntry.workspace) { [string]$agentEntry.workspace } else { "" }
$effectiveWorkspace = if ($repoEnv.ContainsKey("SENTINEL_WORKSPACE_ROOT") -and $repoEnv["SENTINEL_WORKSPACE_ROOT"]) {
    $repoEnv["SENTINEL_WORKSPACE_ROOT"]
}
else {
    $agentWorkspace
}
$configGatewayUrl = Get-GatewayUrlFromConfig -Config $config
$effectiveGatewayUrl = if ($GatewayUrl) {
    $GatewayUrl
}
elseif ($repoEnv.ContainsKey("OPENCLAW_GATEWAY_URL") -and $repoEnv["OPENCLAW_GATEWAY_URL"]) {
    $repoEnv["OPENCLAW_GATEWAY_URL"]
}
elseif ($env:OPENCLAW_GATEWAY_URL) {
    $env:OPENCLAW_GATEWAY_URL
}
else {
    $configGatewayUrl
}
$configGatewayToken = if ($null -ne $config.gateway -and $null -ne $config.gateway.auth) { [string]$config.gateway.auth.token } else { "" }
$effectiveGatewayToken = if ($GatewayToken) {
    $GatewayToken
}
elseif ($repoEnv.ContainsKey("OPENCLAW_GATEWAY_TOKEN") -and $repoEnv["OPENCLAW_GATEWAY_TOKEN"]) {
    $repoEnv["OPENCLAW_GATEWAY_TOKEN"]
}
elseif ($env:OPENCLAW_GATEWAY_TOKEN) {
    $env:OPENCLAW_GATEWAY_TOKEN
}
else {
    $configGatewayToken
}

$responsesEnabled = $false
if ($null -ne $config.gateway `
    -and $null -ne $config.gateway.http `
    -and $null -ne $config.gateway.http.endpoints `
    -and $null -ne $config.gateway.http.endpoints.responses `
    -and $config.gateway.http.endpoints.responses.enabled) {
    $responsesEnabled = [bool]$config.gateway.http.endpoints.responses.enabled
}

Write-Host ("AgentId             : {0}" -f $effectiveAgentId)
Write-Host ("Agent exists        : {0}" -f ($null -ne $agentEntry))
Write-Host ("Agent workspace     : {0}" -f ($(if ($agentWorkspace) { $agentWorkspace } else { "<missing>" })))
Write-Host ("Workspace exists    : {0}" -f ($(if ($effectiveWorkspace) { Test-Path -LiteralPath $effectiveWorkspace } else { $false })))
Write-Host ("Effective workspace : {0}" -f ($(if ($effectiveWorkspace) { $effectiveWorkspace } else { "<missing>" })))
Write-Host ("Config gateway URL  : {0}" -f $configGatewayUrl)
Write-Host ("Effective gateway   : {0}" -f $effectiveGatewayUrl)
Write-Host ("Responses enabled   : {0}" -f $responsesEnabled)
Write-Host ("Gateway token       : {0}" -f (Mask-Secret $effectiveGatewayToken))
if ($null -ne $config.hooks -and $config.hooks.token) {
    Write-Host ("Hooks token         : {0}" -f (Mask-Secret ([string]$config.hooks.token)))
    Write-Host ("Hooks == Gateway    : {0}" -f ([string]$config.hooks.token -eq [string]$configGatewayToken))
}

if ($agentWorkspace -and $effectiveWorkspace) {
    Write-Host ("Workspace match     : {0}" -f ($agentWorkspace -eq $effectiveWorkspace))
}

$port = ([System.Uri]$effectiveGatewayUrl).Port

Write-Section "Listening Port"
Show-PortOwner -Port $port

Write-Section "GET /v1/models"
$modelsUrl = ($effectiveGatewayUrl.TrimEnd("/") + "/v1/models")
$modelsHeaders = @{
    Authorization = "Bearer $effectiveGatewayToken"
}
$modelsResponse = Get-HttpResponse -Method GET -Url $modelsUrl -Headers $modelsHeaders
Write-Host ("Status              : {0} {1}" -f $modelsResponse.StatusCode, $modelsResponse.Reason)
Write-Host ("Content-Type        : {0}" -f $(if ($modelsResponse.ContentType) { $modelsResponse.ContentType } else { "<missing>" }))
$modelsBodyPreview = if ($modelsResponse.Body.Length -gt 1200) { $modelsResponse.Body.Substring(0, 1200) + "...(truncated)" } else { $modelsResponse.Body }
Write-Host "Body preview:"
Write-Host $modelsBodyPreview

$modelsJson = Try-ParseJson -Text $modelsResponse.Body
$modelIds = @()
if ($null -ne $modelsJson -and $null -ne $modelsJson.data) {
    foreach ($item in @($modelsJson.data)) {
        if ($null -ne $item -and $item.PSObject.Properties.Name -contains "id" -and $item.id) {
            $modelIds += [string]$item.id
        }
    }
}
if ($modelIds.Count -gt 0) {
    Write-Host ""
    Write-Host "Model IDs:"
    $modelIds | Sort-Object | ForEach-Object { Write-Host ("- {0}" -f $_) }
}

$expectedModelIds = @("openclaw", "openclaw/default", "openclaw/$effectiveAgentId")
$missingModelIds = @($expectedModelIds | Where-Object { $_ -notin $modelIds })

if ($missingModelIds.Count -gt 0) {
    Write-Host ""
    Write-Host ("Missing expected model ids: {0}" -f ($missingModelIds -join ", "))
}

if ($TestResponses) {
    Write-Section "POST /v1/responses"
    $responsesUrl = ($effectiveGatewayUrl.TrimEnd("/") + "/v1/responses")
    $responsesHeaders = @{
        Authorization        = "Bearer $effectiveGatewayToken"
        "x-openclaw-agent-id" = $effectiveAgentId
        "Content-Type"       = "application/json"
    }
    $responsesBody = @{
        model = "openclaw"
        input = "请只回复一行：OPENCLAW_HTTP_OK"
    } | ConvertTo-Json -Compress

    $responsesResult = Get-HttpResponse -Method POST -Url $responsesUrl -Headers $responsesHeaders -Body $responsesBody
    Write-Host ("Status              : {0} {1}" -f $responsesResult.StatusCode, $responsesResult.Reason)
    Write-Host ("Content-Type        : {0}" -f $(if ($responsesResult.ContentType) { $responsesResult.ContentType } else { "<missing>" }))
    $responsesBodyPreview = if ($responsesResult.Body.Length -gt 1200) { $responsesResult.Body.Substring(0, 1200) + "...(truncated)" } else { $responsesResult.Body }
    Write-Host "Body preview:"
    Write-Host $responsesBodyPreview

    $responsesJson = Try-ParseJson -Text $responsesResult.Body
    if ($null -ne $responsesJson) {
        Write-Host ("Response id         : {0}" -f $responsesJson.id)
        Write-Host ("Response status     : {0}" -f $responsesJson.status)
        Write-Host ("Final text          : {0}" -f (Extract-OutputText -Payload $responsesJson))
    }
}

Write-Section "Summary"
$summaryIssues = New-Object System.Collections.Generic.List[string]
if (-not (Test-Path -LiteralPath $effectiveConfigPath)) {
    [void]$summaryIssues.Add("OpenClaw config file does not exist.")
}
if (-not $responsesEnabled) {
    [void]$summaryIssues.Add("gateway.http.endpoints.responses.enabled is false or missing.")
}
if ($null -eq $agentEntry) {
    [void]$summaryIssues.Add("Agent llm-security-intel is missing from openclaw.json.")
}
if ($effectiveWorkspace -and -not (Test-Path -LiteralPath $effectiveWorkspace)) {
    [void]$summaryIssues.Add("Effective workspace path does not exist.")
}
if (-not $effectiveGatewayToken) {
    [void]$summaryIssues.Add("Gateway token is missing.")
}
if ($modelsResponse.StatusCode -ne 200) {
    [void]$summaryIssues.Add(("GET /v1/models returned HTTP {0}." -f $modelsResponse.StatusCode))
}
if ($modelsResponse.ContentType -notlike "application/json*") {
    [void]$summaryIssues.Add("GET /v1/models did not return JSON.")
}
if ($missingModelIds.Count -gt 0) {
    [void]$summaryIssues.Add(("Expected model ids are missing: {0}" -f ($missingModelIds -join ", ")))
}

if ($summaryIssues.Count -eq 0) {
    Write-Host "No obvious configuration issue found. OpenClaw HTTP Responses looks ready."
    exit 0
}

foreach ($issue in $summaryIssues) {
    Write-Host ("- {0}" -f $issue)
}
exit 2
