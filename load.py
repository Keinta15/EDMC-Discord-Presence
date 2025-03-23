#
# KodeBlox Copyright 2019 Sayak Mukhopadhyay
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http: //www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import functools
import logging
import threading
import tkinter as tk
from os.path import dirname, join
import semantic_version
import sys
import time

import l10n
import myNotebook as nb
from config import config, appname, appversion
from py_discord_sdk import discordsdk as dsdk

plugin_name = "DiscordPresence"

logger = logging.getLogger(f'{appname}.{plugin_name}')

_ = functools.partial(l10n.Translations.translate, context=__file__)

CLIENT_ID = 386149818227097610
VERSION = '3.2.0'

# Global state variables
planet = '<Hidden>'
landingPad = '2'
this = sys.modules[__name__]

def callback(result):
    """Handle Discord SDK callbacks"""
    if result == dsdk.Result.ok:
        logger.debug("Activity update successful")
    else:
        logger.error(f'Discord error: {result.name}')

def update_presence():
    """Update the Discord presence with current state"""
    try:
        core_version = semantic_version.Version(appversion() if callable(appversion) else appversion)
        disabled = (config.getint if core_version < semantic_version.Version('5.0.0-beta1') else config.get_int)("disable_presence")
    except Exception as e:
        logger.error(f"Version check failed: {e}")
        disabled = 0

    if not disabled:
        this.activity.state = this.presence_state
        this.activity.details = this.presence_details
        this.activity.timestamps.start = int(this.time_start)
        this.activity.assets.large_image = 'elite_logo'
        this.activity_manager.update_activity(this.activity, callback)

def plugin_prefs(parent, cmdr, is_beta):
    """Create preferences UI"""
    frame = nb.Frame(parent)
    this.disablePresence = tk.IntVar(value=config.getint("disable_presence"))
    nb.Checkbutton(frame, text="Disable Presence", variable=this.disablePresence).grid()
    nb.Label(frame, text=f'Version {VERSION}').grid(padx=10, pady=10, sticky=tk.W)
    return frame

def prefs_changed(cmdr, is_beta):
    """Save preferences"""
    config.set('disable_presence', this.disablePresence.get())
    update_presence()

def plugin_start3(plugin_dir):
    """Initialize plugin"""
    this.plugin_dir = plugin_dir
    this.discord_thread = threading.Thread(target=initialize_discord, daemon=True)
    this.discord_thread.start()
    return plugin_name

def plugin_stop():
    """Clean up on plugin stop"""
    if hasattr(this, 'activity_manager'):
        this.activity_manager.clear_activity(callback)
    this.running = False

def journal_entry(cmdr, is_beta, system, station, entry, state):
    """Handle journal events"""
    global planet, landingPad

    presence_state = this.presence_state
    presence_details = this.presence_details

    try:
        if entry['event'] == 'StartUp':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at {station}').format(station=station) if station else _('Flying in normal space')

        elif entry['event'] == 'Location':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at {station}').format(station=station) if station else _('Flying in normal space')

        elif entry['event'] == 'StartJump':
            presence_state = _('Jumping')
            if entry['JumpType'] == 'Hyperspace':
                presence_details = _('Jumping to system {system}').format(system=entry['StarSystem'])
            else:
                presence_details = _('Preparing for supercruise')

        elif entry['event'] == 'SupercruiseEntry':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Supercruising')

        elif entry['event'] == 'SupercruiseExit':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Flying in normal space')

        elif entry['event'] == 'FSDJump':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Supercruising')

        elif entry['event'] == 'Docked':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at {station}').format(station=station)

        elif entry['event'] == 'Undocked':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Flying in normal space')

        elif entry['event'] == 'ShutDown':
            presence_state = _('Connecting CMDR Interface')
            presence_details = ''

        elif entry['event'] == 'DockingGranted':
            landingPad = entry['LandingPad']

        elif entry['event'] == 'Music' and entry.get('MusicTrack') == 'MainMenu':
            presence_state = _('Connecting CMDR Interface')
            presence_details = ''

        elif entry['event'] == 'ApproachBody':
            planet = entry['Body']
            presence_details = _('Approaching {body}').format(body=planet)

        elif entry['event'] == 'Touchdown' and entry['PlayerControlled']:
            presence_details = _('Landed on {body}').format(body=planet)

        elif entry['event'] == 'Liftoff':
            if entry['PlayerControlled']:
                presence_details = _('Flying around {body}').format(body=planet)
            else:
                presence_details = _('In SRV on {body}, ship in orbit').format(body=planet)

        elif entry['event'] == 'LeaveBody':
            presence_details = _('Supercruising')

        elif entry['event'] == 'LaunchSRV':
            presence_details = _('In SRV on {body}').format(body=planet)

        elif entry['event'] == 'DockSRV':
            presence_details = _('Landed on {body}').format(body=planet)

        # Odyssey Events
        elif entry['event'] == 'Disembark':
            if entry.get('OnPlanet'):
                body_name = entry.get('Body', planet)
                presence_details = _('On foot at {location}').format(location=body_name)
                planet = body_name
            elif entry.get('OnStation'):
                presence_details = _('On foot at {station}').format(station=station)

        elif entry['event'] == 'Embark':
            if entry.get('Taxi'):
                presence_details = _('Traveling via Apex Taxi')
            elif entry.get('OnPlanet'):
                presence_details = _('Boarding ship at {location}').format(location=planet)

        elif entry['event'] == 'FactionKillBond':
            presence_details = _('Ground combat in {system}').format(system=system)

        elif entry['event'] == 'ApproachConflictZone':
            presence_details = _('Approaching conflict zone')

        elif entry['event'] == 'ConflictZone':
            presence_details = _('Combat ({side})').format(side=entry.get('Side', ''))

        elif entry['event'] == 'ApproachSettlement':
            presence_details = _('Approaching {settlement}').format(settlement=entry['Name'])

        elif entry['event'] == 'SettlementApproached':
            presence_details = _('At {settlement}').format(settlement=entry['Name'])

                if entry['event'] == 'StartUp':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at {station}').format(station=station) if station else _('Flying in normal space')

        elif entry['event'] == 'Location':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at {station}').format(station=station) if station else _('Flying in normal space')

        # Add Fleet Carrier handlers
        elif entry['event'] == 'Docked':
            if entry.get('StationType') == 'FleetCarrier':
                presence_details = _('Docked at Fleet Carrier {station}').format(station=station)
            else:
                presence_details = _('Docked at {station}').format(station=station)
            presence_state = _('In system {system}').format(system=system)

        elif entry['event'] == 'CarrierJumpRequest':
            presence_state = _('Fleet Carrier preparing jump')
            presence_details = _('To {system}').format(system=entry['SystemName'])

        elif entry['event'] == 'CarrierJumpCancelled':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at Fleet Carrier')

        elif entry['event'] == 'CarrierJump':
            presence_state = _('In system {system}').format(system=entry['StarSystem'])
            presence_details = _('Fleet Carrier arrived')

        elif entry['event'] == 'Undocked':
            if entry.get('StationType') == 'FleetCarrier':
                presence_details = _('Flying near Fleet Carrier')
            else:
                presence_details = _('Flying in normal space')
            presence_state = _('In system {system}').format(system=system)

        elif entry['event'] == 'CarrierStats':
            presence_details = _('Managing Fleet Carrier')
            if entry.get('CrewCount', 0) > 0:
                presence_details += f" ({entry['CrewCount']} crew)"

        elif entry['event'] == 'CarrierBankTransfer':
            presence_details = _('Managing Fleet Carrier finances')

        elif entry['event'] == 'CarrierDecommission':
            presence_details = _('Decommissioning Fleet Carrier')
            presence_state = _('In system {system}').format(system=system)

        if presence_state != this.presence_state or presence_details != this.presence_details:
            this.presence_state = presence_state
            this.presence_details = presence_details
            update_presence()
       
        if presence_state != this.presence_state or presence_details != this.presence_details:
            this.presence_state = presence_state
            this.presence_details = presence_details
            update_presence()

    except Exception as e:
        logger.error(f"Error handling journal entry: {e}", exc_info=True)

def initialize_discord():
    """Initialize Discord connection with retry logic"""
    retry_count = 0
    max_retries = 5
    while not hasattr(this, 'app') and retry_count < max_retries:
        try:
            this.app = dsdk.Discord(CLIENT_ID, dsdk.CreateFlags.no_require_discord, join(dirname(this.plugin_dir), plugin_name))
            this.activity_manager = this.app.get_activity_manager()
            this.activity = dsdk.Activity()
            this.call_back_thread = threading.Thread(target=run_callbacks, daemon=True)
            this.call_back_thread.start()
            reset_presence()
            break
        except Exception as e:
            logger.error(f"Discord init failed (attempt {retry_count+1}/{max_retries}): {e}")
            time.sleep(2 ** retry_count)
            retry_count += 1

def reset_presence():
    """Reset presence to default state"""
    this.presence_state = _('Connecting CMDR Interface')
    this.presence_details = ''
    this.time_start = time.time()
    update_presence()

def run_callbacks():
    """Handle Discord callbacks"""
    while True:
        try:
            time.sleep(0.1)
            this.app.run_callbacks()
        except Exception as e:
            logger.error(f"Discord callback failed: {e}")
            time.sleep(1)
            initialize_discord()
            break

# CQC handling (remains from original)
def journal_entry_cqc(cmdr, is_beta, entry, state):
    maps = {
        'Bleae Aewsy GA-Y d1-14': 'Asteria Point',
        'Eta Cephei': 'Cluster Compound',
        'Theta Ursae Majoris': 'Elevate',
        'Boepp SU-E d12-818': 'Ice Field',
    }

    presence_state = this.presence_state
    presence_details = this.presence_details

    try:
        if entry['event'] in ['LoadGame', 'StartUp'] or entry.get('MusicTrack') == 'CQCMenu':
            game_version = 'in Horizons' if state['Horizons'] else 'in Odyssey' if state['Odyssey'] else ''
            presence_state = f'Playing CQC {game_version}'
            presence_details = 'In lobby/queue'

        elif entry['event'] == 'Location' and entry.get('StarSystem'):
            presence_details = maps.get(entry['StarSystem'], '')
            presence_state = f'Playing CQC {game_version}'

        if presence_state != this.presence_state or presence_details != this.presence_details:
            this.presence_state = presence_state
            this.presence_details = presence_details
            update_presence()

def run_callbacks():
    try:
        while True:
            time.sleep(1 / 10)
            this.app.run_callbacks()
    except Exception:
        check_run(this.plugin_dir)
