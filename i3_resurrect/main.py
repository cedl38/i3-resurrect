import json
import sys
import os
import time
from pathlib import Path

import click
import i3ipc
from natsort import natsorted

from . import layout
from . import programs
from . import util


@click.group(context_settings=dict(help_option_names=['-h', '--help'],
                                   max_content_width=150))
@click.version_option()
def main():
    pass


@main.command('save')
@click.option('--workspace', '-w',
              is_flag=True,
              help='The workspaces to save.\n This can either be a name or the number of a workspace.')
@click.option('--numeric', '-n',
              is_flag=True,
              help='Select workspace by number instead of name.')
@click.option('--session', '-S',
              is_flag=True,
              help='Save current session.\n')
@click.option('--directory', '-d',
              type=click.Path(file_okay=False, writable=True),
              default=Path('~/.i3/i3-resurrect/').expanduser(),
              help=('The directory to save the workspace to.\n'
                    '[default: ~/.i3/i3-resurrect]'))
@click.option('--profile', '-p',
              default=None,
              help=('The profile to save the workspace to.'))
@click.option('--clear', '-c',
              is_flag=True,
              help='Clear previous layout files before saving.\n')
@click.option('--swallow', '-s',
              default='class,instance',
              help=('The swallow criteria to use.\n'
                    '[options: class,instance,title,window_role]\n'
                    '[default: class,instance]'))
@click.option('--layout-only', 'target',
              flag_value='layout_only',
              help='Only save layout.')
@click.option('--programs-only', 'target',
              flag_value='programs_only',
              help='Only save running programs.')
@click.argument('workspaces', nargs=-1, default=None)
def save_workspace(workspace, numeric, session, directory, profile, clear, swallow, target, workspaces):
    """
    Save i3 workspace(s) layout(s) or whole session and running programs to a file.

    WORKSPACES are the workspaces to save.
    [default: current workspace]
    """
    i3 = i3ipc.Connection()
    if not workspaces:
        # set default value
        workspaces = ( i3.get_tree().find_focused().workspace().name, )

    if profile is not None:
        directory = Path(directory) / profile

    # Create directory if non-existent.
    Path(directory).mkdir(parents=True, exist_ok=True)

    if target != 'programs_only':
        swallow_criteria = swallow.split(',')

    if clear and os.path.isdir(directory):
        # Clear previous layout files before saving in current profile
        clear_directory(directory, target)

    if session:
        workspaces = layout.list(i3, numeric)
    elif not workspace:
        util.eprint('Either --workspace or --session should be specified.')
        sys.exit(1)

    for workspace_id in workspaces:
        if target != 'programs_only':
            # Save workspace layout to file.
            layout.save(workspace_id, numeric, directory, swallow_criteria)

        if target != 'layout_only':
            # Save running programs to file.
            programs.save(workspace_id, numeric, directory)


def restore_workspace(i3, saved_layout, saved_programs, target, clear):
    if saved_layout == None:
        return

    # Get layout name from file.
    if 'name' in saved_layout:
        workspace_name = saved_layout['name']
    else:
        util.eprint('Workspace name not found.')
        sys.exit(1)

    i3.command(f'workspace --no-auto-back-and-forth {workspace_name}')

    if target != 'programs_only':
        # Load workspace layout.
        layout.restore(workspace_name, saved_layout)

    if target != 'layout_only':
        # Restore programs.
        programs.restore(workspace_name, saved_programs, clear)


@main.command('restore')
@click.option('--workspace', '-w',
              is_flag=True,
              help='The workspace to restore.\nThis can either be a name or the number of a workspace.')
@click.option('--numeric', '-n',
              is_flag=True,
              help='Select workspace by number instead of name.')
@click.option('--session', '-S',
              is_flag=True,
              help='Restore current session.\n')
@click.option('--directory', '-d',
              type=click.Path(file_okay=False),
              default=Path('~/.i3/i3-resurrect/').expanduser(),
              help=('The directory to restore the workspace from.\n'
                    '[default: ~/.i3/i3-resurrect]'))
@click.option('--profile', '-p',
              default=None,
              help=('The profile to restore the workspace from.'))
@click.option('--clear', '-c',
              is_flag=True,
              help='Close program that are not part of the workspace layout \
              before restore it.\n')
@click.option('--focus', '-f',
              is_flag=True,
              help='Keep the focus on the current window.\n')
@click.option('--layout-only', 'target',
              flag_value='layout_only',
              help='Only restore layout.')
@click.option('--programs-only', 'target',
              flag_value='programs_only',
              help='Only restore running programs.')
@click.argument('workspaces', nargs=-1)
def restore_workspaces(workspace, numeric, session, directory, profile, target,
        clear, focus, workspaces):
    """
    Restore i3 workspace(s) layout(s) or whole session and programs.

    WORKSPACES are the workspaces to restore.
    [default: current workspace]
    """
    i3 = i3ipc.Connection()

    focused_workspace = i3.get_tree().find_focused().workspace().name

    if not workspaces:
        if numeric:
            workspaces = ( str(i3.get_tree().find_focused().workspace().num), )
        else:
            workspaces = ( focused_workspace, )

    if profile is not None:
        directory = Path(directory) / profile

    if session:
        # Restore all workspaces from dir
        files = util.list_filenames(directory)
        for layout_file, programs_file in files:
            saved_layout = json.loads(layout_file.read_text())
            if target != 'layout_only':
                saved_programs = json.loads(programs_file.read_text())
            else:
                saved_programs = None
            restore_workspace(i3, saved_layout, saved_programs, target, clear)
    elif workspace:
        for workspace_id in workspaces:
            if numeric and not workspace_id.isdigit():
                util.eprint('Invalid workspace number.')
                sys.exit(1)
            saved_layout = layout.read(workspace_id, directory)
            if target != 'layout_only':
                saved_programs = programs.read(workspace_id, directory)
            else:
                saved_programs = None
            restore_workspace(i3, saved_layout, saved_programs, target, clear)
    else:
        util.eprint('Either --workspace or --session should be specified.')
        sys.exit(1)

    if focus:
        # WORKAROUND: Add time sleep for loading the latest restored programm.
        time.sleep(3)
        i3.command(f'workspace --no-auto-back-and-forth {focused_workspace}')


@main.command('load')
@click.option('--workspace', '-w',
              is_flag=True,
              help='The workspace to load.\nThis can either be a name or the number of a workspace.')
@click.option('--numeric', '-n',
              is_flag=True,
              help='Select workspace by number instead of name.')
@click.option('--directory', '-d',
              type=click.Path(file_okay=False),
              default=Path('~/.i3/i3-resurrect/').expanduser(),
              help=('The directory to restore the workspace from.\n'
                    '[default: ~/.i3/i3-resurrect]'))
@click.option('--profile', '-p',
              default=None,
              help=('The profile to restore the workspace from.'))
@click.option('--clear', '-c',
              is_flag=True,
              help='Close program that are not part of the workspace layout \
              before loading it.\n')
@click.option('--layout-only', 'target',
              flag_value='layout_only',
              help='Only restore layout.')
@click.option('--programs-only', 'target',
              flag_value='programs_only',
              help='Only restore running programs.')
@click.argument('workspace_layout')
@click.argument('target_workspace', required=False)
def load_workspaces(workspace, numeric, directory, profile, target,
        workspace_layout, target_workspace, clear):
    """
    Load i3 workspace layout and programs.

    WORKSPACE_LAYOUT is the workspace file to load.
    TARGET_WORKSPACE is the target workspace
    """
    i3 = i3ipc.Connection()

    if numeric:
        if not workspace_layout.isdigit():
            util.eprint('Invalid workspace number.')
            sys.exit(1)

        if not target_workspace:
            target_workspace = str(i3.get_tree().find_focused().workspace().num)
        elif not target_workspace.isdigit():
            util.eprint('Invalid workspace number.')
            sys.exit(1)
    else:
        target_workspace = i3.get_tree().find_focused().workspace().name

    if profile is not None:
        directory = Path(directory) / profile

    if not workspace:
        util.eprint('--workspace option should be specified.')
        sys.exit(1)

    # Get layout name from file.
    saved_layout = layout.read(workspace_layout, directory)
    if saved_layout == None:
        sys.exit(1)

    if target != 'layout_only':
        saved_programs = programs.read(workspace_layout, directory)
    else:
        saved_programs = None

    if numeric:
        i3.command(f'workspace --no-auto-back-and-forth number \
                {target_workspace}')
    else:
        i3.command(f'workspace --no-auto-back-and-forth {target_workspace}')

    if target != 'programs_only':
        # Load workspace layout.
        layout.restore(target_workspace, saved_layout)

    if target != 'layout_only':
        # Restore programs.
        programs.restore(target_workspace, saved_programs, clear)


@main.command('ls')
@click.option('--directory', '-d',
              type=click.Path(file_okay=False),
              default=Path('~/.i3/i3-resurrect/').expanduser(),
              help=('The directory to search in.\n'
                    '[default: ~/.i3/i3-resurrect]'))
@click.argument('item',
                type=click.Choice(['workspaces', 'profiles']),
                default='workspaces')
def list_workspaces(directory, item):
    """
    List saved workspaces or profiles.
    """
    # TODO: list workspaces in profiles
    if item == 'workspaces':
        directory = Path(directory)
        workspaces = []
        for entry in directory.iterdir():
            if entry.is_file():
                name = entry.name
                name = name[name.index('_') + 1:]
                workspace = name[:name.rfind('_')]
                file_type = name[name.rfind('_') + 1:name.index('.json')]
                workspaces.append(f'Workspace {workspace} {file_type}')
        workspaces = natsorted(workspaces)
        for workspace in workspaces:
            print(workspace)
    else:
        directory = Path(directory)
        profiles = []
        try:
            for entry in directory.iterdir():
                if entry.is_dir():
                    profile = entry.name
                    profiles.append(f'Profile {profile}')
            profiles = natsorted(profiles)
            for profile in profiles:
                print(profile)
        except FileNotFoundError:
            print('No profiles found')


@main.command('rm')
@click.option('--workspace', '-w',
              is_flag=True,
              help='The saved workspace to delete.\nThis can either be a name or the number of a workspace.')
@click.option('--session', '-S',
              is_flag=True,
              help='Delete saved session layout.\n')
@click.option('--directory', '-d',
              type=click.Path(file_okay=False),
              default=Path('~/.i3/i3-resurrect/').expanduser(),
              help=('The directory to delete from.\n'
                    '[default: ~/.i3/i3-resurrect]'))
@click.option('--profile', '-p', default=None, help=('The profile to delete.'))
@click.option('--layout-only', 'target',
              flag_value='layout_only',
              help='Only delete saved layout.')
@click.option('--programs-only', 'target',
              flag_value='programs_only',
              help='Only delete saved programs.')
@click.argument('workspaces', nargs=-1)
def remove(workspace, session, directory, profile, target, workspaces):
    """
    Remove saved worspace(s) layout(s), whole session, or programs.

    WORKSPACES are the workspaces to remove.
    """
    if profile is not None:
        directory = Path(directory) / profile

    if session and os.path.isdir(directory):
        clear_directory(directory, target)
        if profile is not None:
            os.rmdir(directory)
    elif workspace:
        for workspace_id in workspaces:
            workspace_id = util.filename_filter(workspace_id)
            programs_filename = f'workspace_{workspace_id}_programs.json'
            layout_filename = f'workspace_{workspace_id}_layout.json'
            programs_file = Path(directory) / programs_filename
            layout_file = Path(directory) / layout_filename

            delete(layout_file, programs_file, target)
    else:
        util.eprint('either --workspace or --session option should be specified.')
        sys.exit(1)


def delete(layout_file, programs_file, target):
    if target != 'programs_only':
        # Delete programs file.
        programs_file.unlink()

    if target != 'layout_only':
        # Delete layout file.
        layout_file.unlink()


def clear_directory(directory, target):
    '''
    clear saved layout session
    '''
    files = util.list_filenames(directory)
    for layout_file, programs_file in files:
        delete(layout_file, programs_file, target)


@main.command('close')
@click.option('--workspace', '-w',
              is_flag=True,
              help='The workspace to close.\nThis can either be a name or the number of a workspace.')
@click.option('--session', '-S',
              is_flag=True,
              help='Close current session.\n')
@click.argument('workspaces', nargs=-1)
def close(workspace, session, workspaces):
    """
    Close workspace(s) or whole session.
    """
    i3 = i3ipc.Connection()

    if not workspaces:
        workspaces = ( i3.get_tree().find_focused().workspace().name, )

    if session:
        workspaces = layout.list(i3, False)
    elif not workspace:
        util.eprint('either --workspace or --session option should be specified.')
        sys.exit(1)

    for workspace_id in workspaces:
        i3.command(f'[workspace="{workspace_id}"] kill')


if __name__ == '__main__':
    main()
