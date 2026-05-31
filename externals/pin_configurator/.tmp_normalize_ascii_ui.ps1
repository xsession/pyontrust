$ErrorActionPreference = 'Stop'

$indexPath = 'c:\GIT\addmind\deps\pyontrust\externals\pin_configurator\web\index.html'
$mainPath = 'c:\GIT\addmind\deps\pyontrust\externals\pin_configurator\web\main.js'

function Apply-Replacements {
  param(
    [string]$Path,
    [object[]]$Rules
  )

  $text = [System.IO.File]::ReadAllText($Path)
  foreach ($rule in $Rules) {
    $text = [regex]::Replace($text, $rule.Pattern, $rule.Replacement)
  }
  [System.IO.File]::WriteAllText($Path, $text, [System.Text.UTF8Encoding]::new($false))
}

$indexRules = @(
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Module Configurator'; Replacement = '<span class="tab-icon">[MOD]</span>Module Configurator' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>LVGL Layout'; Replacement = '<span class="tab-icon">[GUI]</span>LVGL Layout' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Protocol Editor'; Replacement = '<span class="tab-icon">[PRT]</span>Protocol Editor' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Interrupt Configurator'; Replacement = '<span class="tab-icon">[INT]</span>Interrupt Configurator' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Peripheral Configurator'; Replacement = '<span class="tab-icon">[PER]</span>Peripheral Configurator' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Clock Configurator'; Replacement = '<span class="tab-icon">[CLK]</span>Clock Configurator' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Pin Configurator'; Replacement = '<span class="tab-icon">[PIN]</span>Pin Configurator' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Arduino Importer'; Replacement = '<span class="tab-icon">[ARD]</span>Arduino Importer' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Board Editor'; Replacement = '<span class="tab-icon">[BRD]</span>Board Editor' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Package Manager'; Replacement = '<span class="tab-icon">[PKG]</span>Package Manager' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Sensor Parser'; Replacement = '<span class="tab-icon">[SNS]</span>Sensor Parser' },
  @{ Pattern = '<span class="tab-icon">[^<]*</span>Zephyr Catalog'; Replacement = '<span class="tab-icon">[CAT]</span>Zephyr Catalog' },
  @{ Pattern = '(<button class="zoom-btn" id="boardEditorZoomOut" title="Zoom out">)(.*?)(</button>)'; Replacement = '$1-$3' },
  @{ Pattern = '(<button class="zoom-btn" id="boardEditorZoomFit" title="Fit to area">)(.*?)(</button>)'; Replacement = '$1[]$3' },
  @{ Pattern = '(<button class="zoom-btn" id="zoomOut" title="Zoom out">)(.*?)(</button>)'; Replacement = '$1-$3' },
  @{ Pattern = '(<button class="zoom-btn" id="zoomFit" title="Fit to view">)(.*?)(</button>)'; Replacement = '$1[]$3' }
)

$mainRules = @(
  @{ Pattern = 'direction === "asc" \? " [^"]*" : direction === "desc" \? " [^"]*" : ""'; Replacement = 'direction === "asc" ? " ^" : direction === "desc" ? " v" : ""' },
  @{ Pattern = 'replace\(/\[[^\]]*\]/g, ""\)'; Replacement = 'replace(/[\^v]/g, "")' },
  @{ Pattern = '<button class="btn" id="modResetBtn">[^<]*Reset Module</button>'; Replacement = '<button class="btn" id="modResetBtn">Reset Module</button>' },
  @{ Pattern = '<button class="btn" id="modEnableBtn">\$\{modEnabled\[id\] \? ''.*?'' : ''.*?''\}</button>'; Replacement = '<button class="btn" id="modEnableBtn">${modEnabled[id] ? ''Enabled'' : ''Enable''}</button>' },
  @{ Pattern = '<button class="btn btn-primary" id="modGenerateAllBtn">[^<]*Generate All \(0\)</button>'; Replacement = '<button class="btn btn-primary" id="modGenerateAllBtn">Generate All (0)</button>' },
  @{ Pattern = '<button class="btn" id="modCopyBtn" style="display:none">[^<]*Copy</button>'; Replacement = '<button class="btn" id="modCopyBtn" style="display:none">Copy</button>' },
  @{ Pattern = 'enableBtn\.textContent = modEnabled\[id\] \? ".*?" : ".*?";'; Replacement = 'enableBtn.textContent = modEnabled[id] ? "Enabled" : "Enable";' },
  @{ Pattern = 'btn\.textContent = ".*?Copied!";'; Replacement = 'btn.textContent = "Copied!";' },
  @{ Pattern = 'setTimeout\(\(\) => btn\.textContent = ".*?Copy", 1500\);'; Replacement = 'setTimeout(() => btn.textContent = "Copy", 1500);' },
  @{ Pattern = 'btn\.textContent = ".*?Generating.*?";'; Replacement = 'btn.textContent = "Generating...";' },
  @{ Pattern = 'btn\.textContent = `.*?Generate All \(\$\{count\} module\$\{count !== 1 \? ''s'' : ''''\}\)`;'; Replacement = 'btn.textContent = `Generate All (${count} module${count !== 1 ? ''s'' : ''''})`;' },
  @{ Pattern = '<span class="chevron">[^<]*</span>'; Replacement = '<span class="chevron">v</span>' },
  @{ Pattern = '<div class="icon">[^<]*</div>\s*<div>Peripheral Configurator</div>'; Replacement = '<div class="icon">[PER]</div><div>Peripheral Configurator</div>' },
  @{ Pattern = '<button class="btn" id="pcfgResetBtn">[^<]*Reset</button>'; Replacement = '<button class="btn" id="pcfgResetBtn">Reset</button>' },
  @{ Pattern = '<button class="btn btn-accent" id="pcfgGenerateBtn">[^<]*Generate Config</button>'; Replacement = '<button class="btn btn-accent" id="pcfgGenerateBtn">Generate Config</button>' },
  @{ Pattern = '<button class="btn" id="pcfgCopyBtn" style="display:none">[^<]*Copy</button>'; Replacement = '<button class="btn" id="pcfgCopyBtn" style="display:none">Copy</button>' },
  @{ Pattern = 'sel\.innerHTML = ''<option value="">.*?Select clock tree.*?</option>'';'; Replacement = 'sel.innerHTML = ''<option value="">- Select clock tree -</option>'';' },
  @{ Pattern = '<div class="icon">[^<]*</div>\s*<div>Clock System Configurator</div>'; Replacement = '<div class="icon">[CLK]</div><div>Clock System Configurator</div>' },
  @{ Pattern = '<span class="toggle">[^<]*</span> Warnings'; Replacement = '<span class="toggle">[!]</span> Warnings' },
  @{ Pattern = '>[^<]* \$\{escapeHtml\(warning\)\}</div>'; Replacement = '>- ${escapeHtml(warning)}</div>' },
  @{ Pattern = '<button class="btn btn-accent" id="clkGenerateBtn" onclick="clkGenerate\(\)">[^<]*Generate Config</button>'; Replacement = '<button class="btn btn-accent" id="clkGenerateBtn" onclick="clkGenerate()">Generate Config</button>' },
  @{ Pattern = '<button class="btn" id="clkCopyBtn" style="display:none;" onclick="clkCopyOutput\(\)">[^<]*Copy</button>'; Replacement = '<button class="btn" id="clkCopyBtn" style="display:none;" onclick="clkCopyOutput()">Copy</button>' },
  @{ Pattern = '<span class="toggle">[^<]*</span> Clock Overview'; Replacement = '<span class="toggle">[OV]</span> Clock Overview' },
  @{ Pattern = 'node\.icon \|\| "[^"]*"'; Replacement = 'node.icon || "*"' },
  @{ Pattern = '<span class="toggle">[^<]*</span> Info'; Replacement = '<span class="toggle">[i]</span> Info' },
  @{ Pattern = '<span class="toggle">[^<]*</span> Clock Path'; Replacement = '<span class="toggle">[->]</span> Clock Path' },
  @{ Pattern = '<span class="toggle">[^<]*</span> Configuration'; Replacement = '<span class="toggle">[CFG]</span> Configuration' },
  @{ Pattern = '<span class="toggle">[^<]*</span> Peripheral Assignments'; Replacement = '<span class="toggle">[IO]</span> Peripheral Assignments' },
  @{ Pattern = 'const lines = \["Clock Node Frequencies", ".*?"\.repeat\(50\), ""\];'; Replacement = 'const lines = ["Clock Node Frequencies", "=".repeat(50), ""];' },
  @{ Pattern = 'lines\.push\(".*?"\.repeat\(50\)\);'; Replacement = 'lines.push("-".repeat(50));' },
  @{ Pattern = '←'; Replacement = '<-' },
  @{ Pattern = '<button class="btn" id="snsCopyHeader" style="display:none;">[^<]*Copy</button>'; Replacement = '<button class="btn" id="snsCopyHeader" style="display:none;">Copy</button>' },
  @{ Pattern = '<button class="btn" id="snsGenDriver">[^<]*Generate Zephyr Driver</button>'; Replacement = '<button class="btn" id="snsGenDriver">Generate Zephyr Driver</button>' },
  @{ Pattern = '<h3>[^<]* Description</h3>'; Replacement = '<h3>Description</h3>' },
  @{ Pattern = '<h3>[^<]* Address / Interface</h3>'; Replacement = '<h3>Address / Interface</h3>' },
  @{ Pattern = '<h3>[^<]* Register Map \(\$\{regs\.length\} registers\)</h3>'; Replacement = '<h3>Register Map (${regs.length} registers)</h3>' },
  @{ Pattern = '<h3>[^<]* C Register Header</h3>'; Replacement = '<h3>C Register Header</h3>' },
  @{ Pattern = '<h3>[^<]* Generated Zephyr Driver</h3>'; Replacement = '<h3>Generated Zephyr Driver</h3>' },
  @{ Pattern = 'btn\.textContent = ".*?Generate Zephyr Driver";'; Replacement = 'btn.textContent = "Generate Zephyr Driver";' },
  @{ Pattern = 'resultEl\.innerHTML = `<span style="color:var\(--green\);">.*? \$\{data\.vendor_name\}</span> \(\$\{data\.vendor\}\)`;'; Replacement = 'resultEl.innerHTML = `<span style="color:var(--green);">Vendor: ${data.vendor_name}</span> (${data.vendor})`;' },
  @{ Pattern = 'resultEl\.innerHTML = `<span style="color:var\(--yellow\);">.*? Unknown vendor for "\$\{pn\}"</span>`;'; Replacement = 'resultEl.innerHTML = `<span style="color:var(--yellow);">Unknown vendor for "${pn}"</span>`;' },
  @{ Pattern = '\$\{boardData\.board\} .*? \$\{detectGeneratedFileLanguage\(current\.path\)\}'; Replacement = '${boardData.board} - ${detectGeneratedFileLanguage(current.path)}' },
  @{ Pattern = '\$\{draft\.size\} bytes .*? \$\{new Date\(draft\.updated_at \|\| draft\.created_at\)\.toLocaleString\(\)\}'; Replacement = '${draft.size} bytes - ${new Date(draft.updated_at || draft.created_at).toLocaleString()}' },
  @{ Pattern = 'type \? type \+ ".*?" : ""'; Replacement = 'type ? type + " - " : ""' }
)

Apply-Replacements -Path $indexPath -Rules $indexRules
Apply-Replacements -Path $mainPath -Rules $mainRules
Write-Output 'normalized-frontend-ascii'
