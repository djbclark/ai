#compdef ai
# zsh completion for ai (djbclark/ai)
# Install: source this file, or:
#   eval "$(ai --print-completion zsh)"

_ai() {
  local -a opts
  opts=(
    '--help[show help]'
    '--version[show version]'
    '(-c --config)'{-c,--config}'[services.yaml path]:path:_files'
    '--show-config-path[print default config paths]'
    '--generate-config[write default config files]'
    '--doctor[environment check (also: ai doctor)]'
    '--print-completion[print shell completion]:shell:(bash zsh)'
    '(-t --timeout)'{-t,--timeout}'[force tool timeout seconds]:seconds'
    '--format[output format]:format:(pretty json)'
    '--json[JSON output]'
    '--no-color[disable ANSI colors]'
    '--no-tui[force classic plain-text report]'
    '(-q --quiet)'{-q,--quiet}'[suppress stderr progress]'
    '--alerts-only[recommendations only]'
    '--brief[action plan + errors only]'
    '--no-tokscale[skip tokscale]'
    '--no-cswap[skip cswap]'
    '--no-codexbar[skip codexbar]'
    '--providers[CodexBar providers]:providers'
    '--min-remaining[min remaining percent]:percent'
    '--max-days[max days until reset]:days'
    '--save[write JSON snapshot]:path:_files'
    '--traditional-summary[legacy flat summary]'
    'doctor:environment check'
  )
  _arguments -s -S $opts
}

compdef _ai ai
