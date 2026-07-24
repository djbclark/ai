# bash completion for ai (djbclark/ai)
# Install: source this file, or:
#   eval "$(ai --print-completion bash)"

_ai_completions() {
  local cur prev
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD - 1]}"

  local opts="
    --help --version
    --config -c
    --show-config-path --generate-config --doctor --print-completion
    -t --timeout
    --format --json --no-color --no-tui -q --quiet --alerts-only --brief
    --no-tokscale --no-cswap --no-codexbar
    --providers --min-remaining --max-days --save --traditional-summary
    doctor
  "

  case "${prev}" in
    --format)
      COMPREPLY=($(compgen -W "pretty json" -- "${cur}"))
      return 0
      ;;
    --print-completion)
      COMPREPLY=($(compgen -W "bash zsh" -- "${cur}"))
      return 0
      ;;
    --config | -c | --save)
      COMPREPLY=($(compgen -f -- "${cur}"))
      return 0
      ;;
    -t | --timeout | --min-remaining | --max-days | --providers)
      return 0
      ;;
  esac

  if [[ ${cur} == -* ]]; then
    COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
    return 0
  fi

  # First word may be doctor subcommand synonym
  if [[ ${COMP_CWORD} -eq 1 ]]; then
    COMPREPLY=($(compgen -W "doctor ${opts}" -- "${cur}"))
    return 0
  fi

  COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
}

complete -F _ai_completions ai
