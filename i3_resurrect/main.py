import json
import sys
import os
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
@click.option('--directory', '-d',
              type=click.Path(file_okay=False, writable=True),
              default=Path('~/.i3/i3-resurrect/').expanduser(),
              help=('The directory to save the workspace to.\n'
                    '[default: ~/.i3/i3-resurrect]'))
@click.option('--profile', '-p',
              default=None,
              help=('The profile to save the workspace to.'))
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
def save_workspace(workspace, numeric, directory, profile, swallow, target, workspaces):
    """
    Save i3 workspaces layouts and running programs to a file.
    WORKSPACES are the workspaces to save.
    [default: current workspace]
    """
    if not workspaces:
        i3 = i3ipc.Connection()
        # set default value
        workspaces = ( i3.get_tree().find_focused().workspace().name, )

    if profile is not None:
        directory = Path(directory) / profile

    # Create directory if non-existent.
    Path(directory).mkdir(parents=True, exist_ok=True)

    if target != 'programs_only':
        swallow_criteria = swallow.split(',')

    if workspace:
        for workspace_id in workspaces:
            if target != 'programs_only':
                # Save workspace layout to file.
                layout.save(workspace_id, numeric, directory, swallow_criteria)

            if target != 'layout_only':
                # Save running programs to file.
                programs.save(workspace_id, numeric, directory)
    else:
        util.eprint('--workspace must be specified.')
        sys.exit(1)


def restore_workspace(i3, saved_layout, saved_programs, target):
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
        programs.restore(workspace_name, saved_programs)


@main.command('restore')
@click.option('--workspace', '-w',
              is_flag=True,
              help='The workspace to restore.\nThis can either be a name or the number of a workspace.')
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
@click.option('--layout-only', 'target',
              flag_value='layout_only',
              help='Only restore layout.')
@click.option('--programs-only', 'target',
              flag_value='programs_only',
              help='Only restore running programs.')
@click.argument('workspaces', nargs=-1)
def restore_workspaces(workspace, numeric, directory, profile, target, workspaces):
    """
    Restore i3 workspaces layouts and programs.
    WORKSPACES are the workspaces to restore.
    [default: current workspace]
    """
    i3 = i3ipc.Connection()

    if not workspaces:
        if numeric:
            workspaces = ( str(i3.get_tree().find_focused().workspace().num), )
        else:
            workspaces = ( i3.get_tree().find_focused().workspace().name, )

    if profile is not None:
        directory = Path(directory) / profile

    if workspace:
        for workspace_id in workspaces:
            if numeric and not workspace_id.isdigit():
                util.eprint('Invalid workspace number.')
                sys.exit(1)
            saved_layout = layout.read(workspace_id, directory)
            if target != 'layout_only':
                saved_programs = programs.read(workspace_id, directory)
            else:
                saved_programs = None
            restore_workspace(i3, saved_layout, saved_programs, target)
    else:
        util.eprint('--workspace must be specified.')
        sys.exit(1)


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
@click.option('--layout-only', 'target',
              flag_value='layout_only',
              help='Only restore layout.')
@click.option('--programs-only', 'target',
              flag_value='programs_only',
              help='Only restore running programs.')
@click.argument('workspace_layout')
@click.argument('target_workspace', required=False)
def load_workspaces(workspace, numeric, directory, profile, target,
        workspace_layout, target_workspace):
    """
    Load i3 workspace layout and programs.
    WORKSPACE_LAYOUT is the workspace file to load
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
        programs.restore(target_workspace, saved_programs)


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
def remove(workspace, directory, profile, target, workspaces):
    """
    Remove saved layout or programs.
    WORKSPACES are the workspaces to remove.
    """
    if profile is not None:
        directory = Path(directory) / profile

    if workspace:
        for workspace_id in workspaces:
            workspace_id = util.filename_filter(workspace_id)
            programs_filename = f'workspace_{workspace_id}_programs.json'
            layout_filename = f'workspace_{workspace_id}_layout.json'
            programs_file = Path(directory) / programs_filename
            layout_file = Path(directory) / layout_filename

        delete(layout_file, programs_file, target)
    else:
        util.eprint('--workspace option should be specified.')
        sys.exit(1)


def delete(layout_file, programs_file, target):
    if target != 'programs_only':
        # Delete programs file.
        programs_file.unlink()

    if target != 'layout_only':
        # Delete layout file.
        layout_file.unlink()


if __name__ == '__main__':
    main()
