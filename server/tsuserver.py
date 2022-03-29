# KFO-Server, an Attorney Online server
#
# Copyright (C) 2020 Crystalwarrior <varsash@gmail.com>
#
# Derivative of tsuserver3, an Attorney Online server. Copyright (C) 2016 argoneus <argoneuscze@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from server import database
from server.hub_manager import HubManager
from server.client_manager import ClientManager
from server.emotes import Emotes
from server.discordbot import Bridgebot
from server.exceptions import ClientError, ServerError
from server.network.aoprotocol import AOProtocol
from server.network.aoprotocol_ws import new_websocket_client
from server.network.masterserverclient import MasterServerClient
from server.network.webhooks import Webhooks
from server.constants import remove_URL, dezalgo

import server.logger
import sys
import importlib

import asyncio
import websockets

import geoip2.database

import yaml

import logging

logger = logging.getLogger("debug")


class TsuServer3:
    """The main class for KFO-Server derivative of tsuserver3 server software."""

    def __init__(self):
        self.software = "KFO-Server"
        self.release = 3
        self.major_version = 3
        self.minor_version = 0

        self.config = None
        self.censors = None
        self.allowed_iniswaps = []
        self.char_list = None
        self.char_emotes = None
        self.char_pages_ao1 = None
        self.music_list = []
        self.music_list_ao2 = None
        self.music_pages_ao1 = None
        self.backgrounds = None
        self.zalgo_tolerance = None
        self.ipRange_bans = []
        self.geoIpReader = None
        self.useGeoIp = False
        self.supported_features = [
            "yellowtext",
            "customobjections",
            "prezoom",
            "flipping",
            "fastloading",
            "noencryption",
            "deskmod",
            "evidence",
            "modcall_reason",
            "cccc_ic_support",
            "casing_alerts",
            "arup",
            "looping_sfx",
            "additive",
            "effects",
            "expanded_desk_mods",
            "y_offset",
        ]
        self.command_aliases = {}

        try:
            self.geoIpReader = geoip2.database.Reader(
                "./storage/GeoLite2-ASN.mmdb")
            self.useGeoIp = True
            # on debian systems you can use /usr/share/GeoIP/GeoIPASNum.dat if the geoip-database-extra package is installed
        except FileNotFoundError:
            self.useGeoIp = False

        self.ms_client = None
        sys.setrecursionlimit(50)
        try:
            self.load_config()
            self.load_command_aliases()
            self.load_censors()
            self.load_iniswaps()
            self.load_characters()
            self.load_music()
            self.load_backgrounds()
            self.load_ipranges()
            self.hub_manager = HubManager(self)
        except yaml.YAMLError as exc:
            print("There was a syntax error parsing a configuration file:")
            print(exc)
            print("Please revise your syntax and restart the server.")
            sys.exit(1)
        except OSError as exc:
            print("There was an error opening or writing to a file:")
            print(exc)
            sys.exit(1)
        except Exception as exc:
            print("There was a configuration error:")
            print(exc)
            print("Please check sample config files for the correct format.")
            sys.exit(1)

        self.client_manager = ClientManager(self)
        server.logger.setup_logger(debug=self.config["debug"])

        self.webhooks = Webhooks(self)
        self.bridgebot = None

    def start(self):
        """Start the server."""
        loop = asyncio.get_event_loop_policy().get_event_loop()

        bound_ip = "0.0.0.0"
        if self.config["local"]:
            bound_ip = "127.0.0.1"

        ao_server_crt = loop.create_server(
            lambda: AOProtocol(self), bound_ip, self.config["port"]
        )
        ao_server = loop.run_until_complete(ao_server_crt)

        if self.config["use_websockets"]:
            ao_server_ws = websockets.serve(
                new_websocket_client(
                    self), bound_ip, self.config["websocket_port"]
            )
            asyncio.ensure_future(ao_server_ws)

        if self.config["use_masterserver"]:
            self.ms_client = MasterServerClient(self)
            asyncio.ensure_future(self.ms_client.connect(), loop=loop)

        if self.config["zalgo_tolerance"]:
            self.zalgo_tolerance = self.config["zalgo_tolerance"]

        if "bridgebot" in self.config and self.config["bridgebot"]["enabled"]:
            try:
                self.bridgebot = Bridgebot(
                    self,
                    self.config["bridgebot"]["channel"],
                    self.config["bridgebot"]["hub_id"],
                    self.config["bridgebot"]["area_id"],
                )
                asyncio.ensure_future(
                    self.bridgebot.init(self.config["bridgebot"]["token"]), loop=loop
                )
            except Exception as ex:
                # Don't end the whole server if bridgebot destroys itself
                print(ex)
        asyncio.ensure_future(self.schedule_unbans())

        database.log_misc("start")
        print("Server started and is listening on port {}".format(
            self.config["port"]))

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            print("KEYBOARD INTERRUPT")
            loop.stop()

        database.log_misc("stop")

        ao_server.close()
        loop.run_until_complete(ao_server.wait_closed())
        loop.close()

    async def schedule_unbans(self):
        while True:
            database.schedule_unbans()
            await asyncio.sleep(3600 * 12)

    @property
    def version(self):
        """Get the server's current version."""
        return f"{self.release}.{self.major_version}.{self.minor_version}"

    def new_client(self, transport):
        """
        Create a new client based on a raw transport by passing
        it to the client manager.
        :param transport: asyncio transport
        :returns: created client object
        """
        peername = transport.get_extra_info("peername")[0]

        if self.useGeoIp:
            try:
                geoIpResponse = self.geoIpReader.asn(peername)
                asn = str(geoIpResponse.autonomous_system_number)
            except geoip2.errors.AddressNotFoundError:
                asn = "Loopback"
                pass
        else:
            asn = "Loopback"

        for line, rangeBan in enumerate(self.ipRange_bans):
            if rangeBan != "" and peername.startswith(rangeBan) or asn == rangeBan:
                msg = "BD#"
                msg += "Abuse\r\n"
                msg += f"ID: {line}\r\n"
                msg += "Until: N/A"
                msg += "#%"

                transport.write(msg.encode("utf-8"))
                raise ClientError

        c = self.client_manager.new_client(transport)
        c.server = self
        c.area = self.hub_manager.default_hub().default_area()
        c.area.new_client(c)
        return c

    def remove_client(self, client):
        """
        Remove a disconnected client.
        :param client: client object

        """
        if client.area:
            area = client.area
            if (
                not area.dark
                and not area.force_sneak
                and not client.sneaking
                and not client.hidden
            ):
                area.broadcast_ooc(
                    f"[{client.id}] {client.showname} has disconnected.")
            area.remove_client(client)
        self.client_manager.remove_client(client)

    @property
    def player_count(self):
        """Get the number of non-spectating clients."""
        return len(
            [client for client in self.client_manager.clients if client.char_id != -1]
        )

    def load_config(self):
        """Load the main server configuration from a YAML file."""
        try:
            with open("config/config.yaml", "r", encoding="utf-8") as cfg:
                self.config = yaml.safe_load(cfg)
                self.config["motd"] = self.config["motd"].replace("\\n", " \n")
        except OSError:
            print("error: config/config.yaml wasn't found.")
            print("You are either running from the wrong directory, or")
            print("you forgot to rename config_sample (read the instructions).")
            sys.exit(1)

        if "music_change_floodguard" not in self.config:
            self.config["music_change_floodguard"] = {
                "times_per_interval": 1,
                "interval_length": 0,
                "mute_length": 0,
            }
        if "wtce_floodguard" not in self.config:
            self.config["wtce_floodguard"] = {
                "times_per_interval": 1,
                "interval_length": 0,
                "mute_length": 0,
            }

        if "zalgo_tolerance" not in self.config:
            self.config["zalgo_tolerance"] = 3

        if isinstance(self.config["modpass"], str):
            self.config["modpass"] = {"default": {
                "password": self.config["modpass"]}}
        if "multiclient_limit" not in self.config:
            self.config["multiclient_limit"] = 16
        if "asset_url" not in self.config:
            self.config["asset_url"] = ""
        if "block_repeat" not in self.config:
            self.config["block_repeat"] = True

    def load_command_aliases(self):
        """Load a list of banned words to scrub from chats."""
        try:
            with open(
                "config/command_aliases.yaml", "r", encoding="utf-8"
            ) as command_aliases:
                self.command_aliases = yaml.safe_load(command_aliases)
        except:
            logger.debug("Cannot find command_aliases.yaml")

    def load_censors(self):
        """Load a list of banned words to scrub from chats."""
        try:
            with open("config/censors.yaml", "r", encoding="utf-8") as censors:
                self.censors = yaml.safe_load(censors)
        except:
            logger.debug("Cannot find censors.yaml")

    def load_characters(self):
        """Load the character list from a YAML file."""
        with open("config/characters.yaml", "r", encoding="utf-8") as chars:
            self.char_list = yaml.safe_load(chars)
        self.build_char_pages_ao1()
        self.char_emotes = {char: Emotes(char) for char in self.char_list}

    def load_music(self):
        self.build_music_list()
        self.music_pages_ao1 = self.build_music_pages_ao1(self.music_list)
        self.music_list_ao2 = self.build_music_list_ao2(self.music_list)

    def load_backgrounds(self):
        """Load the backgrounds list from a YAML file."""
        with open("config/backgrounds.yaml", "r", encoding="utf-8") as bgs:
            self.backgrounds = yaml.safe_load(bgs)

    def load_iniswaps(self):
        """Load a list of characters for which INI swapping is allowed."""
        try:
            with open("config/iniswaps.yaml", "r", encoding="utf-8") as iniswaps:
                self.allowed_iniswaps = yaml.safe_load(iniswaps)
        except:
            logger.debug("Cannot find iniswaps.yaml")

    def load_ipranges(self):
        """Load a list of banned IP ranges."""
        try:
            with open("config/iprange_ban.txt", "r", encoding="utf-8") as ipranges:
                self.ipRange_bans = ipranges.read().splitlines()
        except:
            logger.debug("Cannot find iprange_ban.txt")

    def build_char_pages_ao1(self):
        """
        Cache a list of characters that can be used for the
        AO1 connection handshake.
        """
        self.char_pages_ao1 = [
            self.char_list[x: x + 10] for x in range(0, len(self.char_list), 10)
        ]
        for i in range(len(self.char_list)):
            self.char_pages_ao1[i // 10][i % 10] = "{}#{}&&0&&&0&".format(
                i, self.char_list[i]
            )

    def build_music_list(self):
        with open("config/music.yaml", "r", encoding="utf-8") as music:
            self.music_list = yaml.safe_load(music)

    def build_music_pages_ao1(self, music_list):
        song_list = []
        index = 0
        for item in music_list:
            if "category" not in item:
                continue
            song_list.append("{}#{}".format(index, item["category"]))
            index += 1
            for song in item["songs"]:
                song_list.append("{}#{}".format(index, song["name"]))
                index += 1
        song_list = [song_list[x: x + 10]
                     for x in range(0, len(song_list), 10)]
        return song_list

    def build_music_list_ao2(self, music_list):
        song_list = []
        for item in music_list:
            if "category" not in item:  # skip settings n stuff
                continue
            song_list.append(item["category"])
            for song in item["songs"]:
                song_list.append(song["name"])
        return song_list

    def is_valid_char_id(self, char_id):
        """
        Check if a character ID is a valid one.
        :param char_id: character ID
        :returns: True if within length of character list; False otherwise

        """
        return len(self.char_list) > char_id >= 0

    def get_char_id_by_name(self, name):
        """
        Get a character ID by the name of the character.
        :param name: name of character
        :returns: Character ID

        """
        for i, ch in enumerate(self.char_list):
            if ch.lower() == name.lower():
                return i
        raise ServerError("Character not found.")

    def get_song_data(self, music_list, music):
        """
        Get information about a track, if exists.
        :param music_list: music list to search
        :param music: track name
        :returns: tuple (name, length or -1)
        :raises: ServerError if track not found
        """
        for item in music_list:
            if "category" not in item:  # skip settings n stuff
                continue
            if item["category"] == music:
                return item["category"], 0
            for song in item["songs"]:
                if song["name"] == music:
                    try:
                        return song["name"], song["length"]
                    except KeyError:
                        return song["name"], 0
        raise ServerError("Music not found.")

    def get_song_is_category(self, music_list, music):
        """
        Get whether a track is a category.
        :param music_list: music list to search
        :param music: track name
        :returns: bool
        """
        for item in music_list:
            if "category" not in item:  # skip settings n stuff
                continue
            if item["category"] == music:
                return True
        return False

    def send_all_cmd_pred(self, cmd, *args, pred=lambda x: True):
        """
        Broadcast an AO-compatible command to all clients that satisfy
        a predicate.
        """
        for client in self.client_manager.clients:
            if pred(client):
                client.send_command(cmd, *args)

    def broadcast_global(self, client, msg, as_mod=False):
        """
        Broadcast an OOC message to all clients that do not have
        global chat muted.
        :param client: sender
        :param msg: message
        :param as_mod: add moderator prefix (Default value = False)

        """
        if as_mod:
            as_mod = "[M]"
        else:
            as_mod = ""
        ooc_name = (
            f"<dollar>G[{client.area.area_manager.abbreviation}]|{as_mod}{client.name}"
        )
        self.send_all_cmd_pred("CT", ooc_name, msg,
                               pred=lambda x: not x.muted_global)

    def send_modchat(self, client, msg):
        """
        Send an OOC message to all mods.
        :param client: sender
        :param msg: message

        """
        ooc_name = "{}[{}][{}]".format(
            "<dollar>M", client.area.id, client.name)
        self.send_all_cmd_pred("CT", ooc_name, msg, pred=lambda x: x.is_mod)

    def broadcast_need(self, client, msg):
        """
        Broadcast an OOC "need" message to all clients who do not
        have advertisements muted.
        :param client: sender
        :param msg: message

        """
        self.send_all_cmd_pred(
            "CT",
            self.config["hostname"],
            f"=== Advert ===\r\n{client.name} in {client.area.name} [{client.area.id}] (Hub {client.area.area_manager.id}) needs {msg}\r\n===============",
            "1",
            pred=lambda x: not x.muted_adverts,
        )

    def send_arup(self, client, args):
        """Update the area properties for this 2.6 client.

        Playercount:
            ARUP#0#<area1_p: int>#<area2_p: int>#...
        Status:
            ARUP#1#<area1_s: string>#<area2_s: string>#...
        CM:
            ARUP#2#<area1_cm: string>#<area2_cm: string>#...
        Lockedness:
            ARUP#3#<area1_l: string>#<area2_l: string>#...

        :param args:

        """
        if len(args) < 2:
            # An argument count smaller than 2 means we only got the identifier of ARUP.
            return
        if args[0] not in (0, 1, 2, 3):
            return

        if args[0] == 0:
            for part_arg in args[1:]:
                try:
                    int(part_arg)
                except:
                    return
        elif args[0] in (1, 2, 3):
            for part_arg in args[1:]:
                try:
                    str(part_arg)
                except:
                    return

        client.send_command("ARUP", *args)

    def send_discord_chat(self, name, message, hub_id=0, area_id=0):
        area = self.hub_manager.get_hub_by_id(hub_id).get_area_by_id(area_id)
        cid = self.get_char_id_by_name(self.config["bridgebot"]["character"])
        message = dezalgo(message)
        message = remove_URL(message)
        message = (
            message.replace("}", "\\}")
            .replace("{", "\\{")
            .replace("`", "\\`")
            .replace("|", "\\|")
            .replace("~", "\\~")
            .replace("º", "\\º")
            .replace("№", "\\№")
            .replace("√", "\\√")
            .replace("\\s", "")
            .replace("\\f", "")
        )
        message = self.config["bridgebot"]["prefix"] + message
        if len(name) > 14:
            name = name[:14].rstrip() + "."
        area.send_ic(
            None,
            "1",
            0,
            self.config["bridgebot"]["character"],
            self.config["bridgebot"]["emote"],
            message,
            self.config["bridgebot"]["pos"],
            "",
            0,
            cid,
            0,
            0,
            [0],
            0,
            0,
            0,
            name,
            -1,
            "",
            "",
            0,
            0,
            0,
            0,
            "0",
            0,
            "",
            "",
            "",
            0,
            "",
        )

    def refresh(self):
        """
        Refresh as many parts of the server as possible:
         - MOTD
         - Mod credentials (unmodding users if necessary)
         - Censors
         - Characters
         - Music
         - Backgrounds
         - Commands
         - Banlists
        """
        with open("config/config.yaml", "r") as cfg:
            cfg_yaml = yaml.safe_load(cfg)
            self.config["motd"] = cfg_yaml["motd"].replace("\\n", " \n")

            # Reload moderator passwords list and unmod any moderator affected by
            # credential changes or removals
            if isinstance(self.config["modpass"], str):
                self.config["modpass"] = {
                    "default": {"password": self.config["modpass"]}
                }
            if isinstance(cfg_yaml["modpass"], str):
                cfg_yaml["modpass"] = {"default": {
                    "password": cfg_yaml["modpass"]}}

            for profile in self.config["modpass"]:
                if (
                    profile not in cfg_yaml["modpass"]
                    or self.config["modpass"][profile] != cfg_yaml["modpass"][profile]
                ):
                    for client in filter(
                        lambda c: c.mod_profile_name == profile,
                        self.client_manager.clients,
                    ):
                        client.is_mod = False
                        client.mod_profile_name = None
                        database.log_misc("unmod.modpass", client)
                        client.send_ooc(
                            "Your moderator credentials have been revoked.")
            self.config["modpass"] = cfg_yaml["modpass"]

        self.load_command_aliases()
        self.load_censors()
        self.load_characters()
        self.load_iniswaps()
        self.load_music()
        self.load_backgrounds()
        self.load_ipranges()

        import server.commands

        importlib.reload(server.commands)
        server.commands.reload()
