$v=@{}
foreach($l in Get-Content "C:\dev\swytchcode\swytchcode-refund-agent-demo\.env"){ 
    if($l -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$'){ 
        $v[$matches[1]]=$matches[2].Trim() 
    } 
}
$env:STRIPE_API_KEY=$v['STRIPE_SECRET_KEY']
$env:HUBSPOT_CRM_CONTACTS_API_KEY=$v['HUBSPOT_PRIVATE_APP_TOKEN']
$env:RESEND_API_KEY=$v['RESEND_API_KEY']

Write-Host "Starting OpenClaw gateway with mapped environment variables..."
openclaw gateway --port 18789
