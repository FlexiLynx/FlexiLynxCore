#!/bin/python3

#> Imports
import os
import sys
import click
import shlex
import logging
from pathlib import Path
from inspect import cleandoc
from importlib import util as iutil
#</Imports

# Get entrypoint
if ep := os.getenv('FLEXILYNX_ENTRYPOINT', None): p = Path(ep)
elif (p := Path('__entrypoint__.py')).exists(): pass
elif (p := Path('../__entrypoint__.py')).exists(): pass
else:
    raise FileNotFoundError('Could not find __entrypoint__.py or ../__entrypoint__.py, maybe set FLEXILYNX_ENTRYPOINT in env?')
sys.path.append(p.parent.as_posix())
__entrypoint__ = iutil.spec_from_file_location('__entrypoint__', p.as_posix()) \
                     .loader.load_module()

#> Header
__entrypoint__.__init__()
from FlexiLynx import logger as fllogger
from FlexiLynx.core import loglib

# Helper functions
def preview(colors: dict):
    for n,f in colors.items():
        click.echo(loglib.colorfmt_from_str(f).format(f'- {n}: {f}'))

# Interactive parts
def iact_logger_colors() -> tuple[str, ...]:
    click.echo('Defaults:')
    preview(loglib.ColoredFormatter._default_colors)
    colors = {l: loglib.LoggerConfig.get(f'color.{l.lower()}', dc) for l,dc in loglib.ColoredFormatter._default_colors.items()}
    click.echo('Current:')
    preview(colors)
    click.echo()
    while True:
        inp = click.prompt('- "help" for help on color formats\n'
                           '- "list" to list prefixes and colors\n'
                           '- "preview" to render preview\n'
                           '- "preview fg[b]" to render preview of foreground ["brightened"] colors\n'
                           '- "preview bg[b]" to render preview of background ["brightened"] colors\n'
                           '- "q[uit]" to stop choosing colors\n'
                           'Enter a log-prefix or command', prompt_suffix=' > ').lower()
        if inp == 'preview':
            preview(colors)
            continue
        elif ((isp := inp.split(' '))[0] == 'preview') and (isp[1] in {'fg', 'fgb', 'bg', 'bgb'}):
            col = getattr(loglib, f'{isp[1].upper()}Colors')
            for c in loglib._raw_colors.keys():
                if c.startswith('_'): continue
                click.echo(getattr(col, c).render(c))
            continue
        elif inp == 'help':
            click.echo(cleandoc(
                loglib.colorfmt_from_str.__doc__.replace(
                    'Handles colors from a structured string, returning a string to be used with `str.format()`', '').strip()))
            continue
        elif inp == 'list':
            click.echo('Colors:')
            for c in loglib._raw_colors.keys():
                if c.startswith('_'): continue
                click.echo(f'- {c}')
            click.echo('Levels:')
            for l in loglib.ColoredFormatter._default_colors.keys(): click.echo(f'- {l}')
            continue
        elif inp.startswith('q'): break
        elif inp.upper() not in colors:
            click.echo(f'Unknown log-level or command {inp!r}')
            continue
        while True:
            col = click.prompt('Enter the color-string', prompt_suffix=' > ', default='', show_default=False)
            try:
                click.echo(loglib.colorfmt_from_str(col).format(f'{inp.upper()}: {col}'))
            except Exception as e:
                click.echo(f'Failed with {e!r}, probably a bad input?')
                continue
            if (cmd := click.prompt('Does this look correct? (Y/n/c[ancel])', prompt_suffix=' > ', default='y', show_default=False).lower()).startswith('n'): continue
            elif cmd.startswith('c'): break
            colors[inp.upper()] = col
            break
    if not click.prompt('Export defaults as well? (y/N)', prompt_suffix=' > ', default='n', show_default=False).lower().startswith('y'):
        colors = {l: c for l,c in colors.items() if loglib.ColoredFormatter._default_colors[l] != c}
    return tuple(f'color.{l.lower()}={c}' for l,c in colors.items())
def iact_logger_verbosity() -> tuple[str, ...]:
    click.echo(f'Current verbosity: {logging.getLevelName(fllogger.getEffectiveLevel())}')
    return (f'verbosity={click.prompt("Input minimum level to log", prompt_suffix=" > ", type=click.Choice(loglib.VERBOSITY_LEVELS, case_sensitive=False)).lower()}',)
#</Header

#> Main >/
cli = click.Group(context_settings={'help_option_names': ('-h', '--help', '-?'), 'max_content_width': 160})

# Logger
@cli.command()
@click.option('-c', '--config', type=click.Choice(('colors', 'verbosity')), help='Add a "thing" to configure (defaults to only "colors" and "verbosity")', default=('colors', 'verbosity'), multiple=True)
@click.option('-f', '--to-file', help='Write to a env-config file (at ./FLLOGCFG.flynx.env) instead of environment variable in stdout', is_flag=True, default=False)
def logger(*, config: tuple[str, ...], to_file: bool):
    '''Interactively configure FlexiLynx\'s logger'''
    cfg = ()
    # Colors
    if 'colors' in config: cfg += iact_logger_colors()
    # Verbosity
    if 'verbosity' in config: cfg += iact_logger_verbosity()
    # Render
    if to_file:
        click.echo(f'Wrote {Path("./FLLOGCFG.flynx.env").write_text("\n".join(cfg))} byte(s) to ./FLLOGCFG.flynx.env')
        return
    click.echo(f'FLLOGCFG={shlex.quote(" ".join(cfg))}')
        
# Main #
cli()
