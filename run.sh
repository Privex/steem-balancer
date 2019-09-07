#!/usr/bin/env bash
################################################################
#                                                              #
#              Production runner script for:                   #
#                                                              #
#                  Steem Load Balancer                         #
#            (C) 2019 Privex Inc.   GNU AGPL v3                #
#                                                              #
#      Privex Site: https://www.privex.io/                     #
#                                                              #
#      Github Repo: https://github.com/Privex/steem-balancer   #
#                                                              #
################################################################

BOLD="$(tput bold)" RED="$(tput setaf 1)" GREEN="$(tput setaf 2)" YELLOW="$(tput setaf 3)" BLUE="$(tput setaf 4)"
MAGENTA="$(tput setaf 5)" CYAN="$(tput setaf 6)" WHITE="$(tput setaf 7)" RESET="$(tput sgr0)"

# easy coloured messages function
# written by @someguy123
function msg () {
    # usage: msg [color] message
    if [[ "$#" -eq 0 ]]; then echo ""; return; fi;
    if [[ "$#" -eq 1 ]]; then
        echo -e "$1"
        return
    fi

    ts="no"
    if [[ "$#" -gt 2 ]] && [[ "$1" == "ts" ]]; then
        ts="yes"
        shift
    fi
    if [[ "$#" -gt 2 ]] && [[ "$1" == "bold" ]]; then
        echo -n "${BOLD}"
        shift
    fi
    [[ "$ts" == "yes" ]] && _msg="[$(date +'%Y-%m-%d %H:%M:%S %Z')] ${@:2}" || _msg="${@:2}"

    case "$1" in
        bold) echo -e "${BOLD}${_msg}${RESET}";;
        [Bb]*) echo -e "${BLUE}${_msg}${RESET}";;
        [Yy]*) echo -e "${YELLOW}${_msg}${RESET}";;
        [Rr]*) echo -e "${RED}${_msg}${RESET}";;
        [Gg]*) echo -e "${GREEN}${_msg}${RESET}";;
        * ) echo -e "${_msg}";;
    esac
}



######
# Directory where the script is located, so we can source files regardless of where PWD is
######

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$DIR"

[[ -f .env ]] && source .env || msg yellow " >> Warning: No .env file found."

# Override these defaults inside of `.env`
: ${HOST='127.0.0.1'}
: ${PORT='8484'}
: ${GU_WORKERS='10'}    # Number of Gunicorn worker processes

case "$1" in
    dev*)
        QUART_APP=wsgi FLASK_ENV=development ./wsgi.py
        ;;
    prod*)
        pipenv run hypercorn -b "${HOST}:${PORT}" -w "$GU_WORKERS" wsgi
        ;;
    *)
        echo "Runner script for Privex's Steem Load Balancer"
        echo ""
        msg bold red "Unknown command.\n"
        msg bold green "Steem Load Balancer - (C) 2019 Privex Inc."
        msg bold green "    Website: https://www.privex.io/ \n    Source: https://github.com/Privex/steem-balancer\n"
        msg green "Available run.sh commands:\n"
        msg yellow "\t dev - Start the Flask development server - UNSAFE FOR PRODUCTION"
        msg yellow "\t prod - Start the production Gunicorn server"
        msg
        ;;
esac
