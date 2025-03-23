#
# KodeBlox Copyright 2019 Sayak Mukhopadhyay
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
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
MAX_RETRIES = 5

# Global state
planet = '<Hidden>'
landingPad = '2'
this = sys.modules[__name__]

def callback(result):
    if result == dsdk.Result.ok:
        logger.debug("Activity updated")
    else:
        logger.error(f'Discord error: {result.name}')

def update_presence():
    if config.get_int("disable_presence") == 0:
        this.activity.state = this.presence_state
        this.activity.details = this.presence_details
        this.activity.timestamps.start = int(this.time_start)
        this.activity.assets.large_image = 'elite_logo'
        this.activity_manager.update_activity(this.activity, callback)
    else:
        this.activity_manager.clear_activity(callback)

def plugin_prefs(parent, cmdr, is_beta):
    this.disablePresence = tk.IntVar(value=config.get_int("disable_presence"))
    frame = nb.Frame(parent)
    nb.Checkbutton(frame, text="Disable Presence", variable=this.disablePresence).grid()
    nb.Label(frame, text=f'Version {VERSION}').grid(padx=10, pady=10, sticky=tk.W)
    return frame

def prefs_changed(cmdr, is_beta):
    try:
        config.set('disable_presence', int(this.disablePresence.get()))
    except ValueError:
        logger.error("Invalid disable_presence value")
    update_presence()

def plugin_start3(plugin_dir):
    this.plugin_dir = plugin_dir
    this.discord_thread = threading.Thread(target=check_run, daemon=True)
    this.discord_thread.start()
    return plugin_name

def plugin_stop():
    if hasattr(this, 'activity_manager'):
        this.activity_manager.clear_activity(callback)
    if hasattr(this, 'call_back_thread'):
        this.call_back_thread.join(timeout=1)

def journal_entry(cmdr, is_beta, system, station, entry, state):
    global planet, landingPad
    original_state = (this.presence_state, this.presence_details)
    
    try:
        event = entry['event']
        presence_state = this.presence_state
        presence_details = this.presence_details

        # Base game events
        if event == 'StartUp':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at {station}').format(station=station) if station else _('Flying in normal space')
        elif event == 'Location':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at {station}').format(station=station) if station else _('Flying in normal space')
        elif event == 'StartJump':
            presence_state = _('Jumping')
            presence_details = (_('Jumping to system {system}').format(system=entry['StarSystem']) 
                              if entry['JumpType'] == 'Hyperspace' 
                              else _('Preparing for supercruise'))
        elif event == 'SupercruiseEntry':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Supercruising')
        elif event == 'SupercruiseExit':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Flying in normal space')
        elif event == 'FSDJump':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Supercruising')
        elif event == 'Docked':
            presence_state = _('In system {system}').format(system=system)
            presence_details = (_('Docked at Fleet Carrier {station}').format(station=station) 
                              if entry.get('StationType') == 'FleetCarrier' 
                              else _('Docked at {station}').format(station=station))
        elif event == 'Undocked':
            presence_state = _('In system {system}').format(system=system)
            presence_details = (_('Flying near Fleet Carrier') 
                              if entry.get('StationType') == 'FleetCarrier' 
                              else _('Flying in normal space'))
        elif event == 'ShutDown':
            presence_state = _('Connecting CMDR Interface')
            presence_details = ''
        elif event == 'DockingGranted':
            landingPad = entry['LandingPad']
        elif event == 'Music' and entry.get('MusicTrack') == 'MainMenu':
            presence_state = _('Connecting CMDR Interface')
            presence_details = ''
        elif event == 'ApproachBody':
            planet = entry['Body']
            presence_details = _('Approaching {body}').format(body=planet)
        elif event == 'Touchdown' and entry.get('PlayerControlled'):
            presence_details = _('Landed on {body}').format(body=planet)
        elif event == 'Liftoff':
            presence_details = (_('Flying around {body}').format(body=planet) 
                              if entry.get('PlayerControlled') 
                              else _('In SRV on {body}, ship in orbit').format(body=planet))
        elif event == 'LeaveBody':
            presence_details = _('Supercruising')
        elif event == 'LaunchSRV':
            presence_details = _('In SRV on {body}').format(body=planet)
        elif event == 'DockSRV':
            presence_details = _('Landed on {body}').format(body=planet)

        # Fleet Carrier Events
        elif event == 'CarrierJumpRequest':
            presence_state = _('Fleet Carrier preparing jump')
            presence_details = _('To {system}').format(system=entry['SystemName'])
        elif event == 'CarrierJumpCancelled':
            presence_state = _('In system {system}').format(system=system)
            presence_details = _('Docked at Fleet Carrier')
        elif event == 'CarrierJump':
            presence_state = _('In system {system}').format(system=entry['StarSystem'])
            presence_details = _('Fleet Carrier arrived')

        # Odyssey Events
        elif event == 'Disembark':
            if entry.get('OnPlanet'):
                presence_details = _('On foot at {body}').format(body=entry.get('Body', planet))
            elif entry.get('OnStation'):
                presence_details = _('On foot at {station}').format(station=station)
        elif event == 'Embark':
            if entry.get('Taxi'):
                presence_details = _('Traveling via Apex Taxi')
            elif entry.get('OnPlanet'):
                presence_details = _('Boarding ship at {location}').format(location=planet)
        elif event == 'FactionKillBond':
            presence_details = _('Ground combat in {system}').format(system=system)
        elif event == 'ApproachSettlement':
            presence_details = _('Approaching {settlement}').format(settlement=entry['Name'])

        # Update only if changed
        if (presence_state, presence_details) != original_state:
            this.presence_state = presence_state
            this.presence_details = presence_details
            update_presence()

    except Exception as e:
        logger.error(f"Journal error: {e}", exc_info=True)

def check_run():
    retry_count = 0
    plugin_path = join(dirname(this.plugin_dir), plugin_name)
    
    while retry_count < MAX_RETRIES:
        try:
            this.app = dsdk.Discord(CLIENT_ID, dsdk.CreateFlags.no_require_discord, plugin_path)
            this.activity_manager = this.app.get_activity_manager()
            this.activity = dsdk.Activity()
            
            this.call_back_thread = threading.Thread(target=run_callbacks, daemon=True)
            this.call_back_thread.start()
            
            this.presence_state = _('Connecting CMDR Interface')
            this.presence_details = ''
            this.time_start = time.time()
            update_presence()
            return
            
        except dsdk.DiscordException as e:
            logger.error(f"Connection failed (attempt {retry_count+1}/{MAX_RETRIES}): {e}")
            retry_count += 1
            time.sleep(min(2 ** retry_count, 60))
    
    logger.critical("Failed to connect to Discord after %d attempts", MAX_RETRIES)

def run_callbacks():
    while True:
        try:
            time.sleep(0.1)
            this.app.run_callbacks()
        except Exception as e:
            logger.error(f"Callback error: {e}")
            check_run()
            break

def plugin_app_version():
    return "5.0.0"
