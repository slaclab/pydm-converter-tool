import logging
import pprint
import re
import textwrap
from pathlib import Path
from pydmconverter.edm.parser import EDMObject

logger = logging.getLogger(__name__)


def generate_menumux_file(
    menumux_buttons: list[EDMObject], output_path: str | Path, loc_declarations: dict[str, str] | None = None
):
    """Write the PyDM screen that embeds the converted .ui under the menus.

    loc_declarations maps a bare local variable address (loc://name) to the
    address that configures it in the converted .ui, so a menu whose controlPv
    names the variable declares it the same way.
    """
    output_path = Path(output_path)
    file_path = output_path.with_suffix(".py")
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # The screen gets its menus as plain literals, so it runs with only qtpy and
    # pydm installed: position, item labels, (macro, value per item) pairs, the
    # EDM initialState and the controlPv address.
    menus = []
    for obj in menumux_buttons:
        count = menu_item_count(obj)
        macros = menu_macros(obj, count)
        menus.append(
            {
                "x": obj.x,
                "y": obj.y,
                "width": obj.width,
                "height": obj.height,
                "items": menu_items(obj, count, macros),
                "macros": macros,
                "initialState": str(obj.properties.get("initialState", "0")),
                "controlPv": control_pv(obj, loc_declarations or {}),
            }
        )
    menus_literal = textwrap.indent(pprint.pformat(menus, width=100, sort_dicts=False), " " * 8).lstrip()

    # The .ui sits next to the generated .py, and PyDM resolves an embedded
    # display's relative filename against the .py's directory.
    code = f"""from qtpy.QtWidgets import (
    QVBoxLayout, QComboBox, QWidget, QStackedLayout
)
from qtpy.QtCore import QCoreApplication, QObject, Signal
from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.rules import unregister_widget_rules
from functools import partial
import json
import re


class ControlPvWriter(QObject):
    # A menu's controlPv channel writes each index emitted here to the PV.
    send_value_signal = Signal(int)


def disconnect_channels(channels, *args):
    # The channels call back into the screen, so they go with it.
    for channel in channels:
        channel.disconnect()


class MenuMuxScreen(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)

        self.muxes = []
        self.menus = {menus_literal}
        self.macro_mappings = []  # Each entry: [(macro_name, [value0, value1, ...]), ...]
        self.current_macros = dict()  # Dict of current macros to apply
        self.control_addresses = []  # Each entry: the menu's controlPv address, or None without one
        self.control_writers = []  # Each entry: the menu's ControlPvWriter, or None without a controlPv
        self.control_channels = []
        self.control_connections = []  # Each entry: whether the menu's controlPv is connected
        self.controls_connected = False
        self.showing_control_value = False

        self.container = QWidget()
        self.stack_layout = QStackedLayout(self.container)

        self.embedded = PyDMEmbeddedDisplay()
        self.embedded.loadWhenShown = True
        self.embedded.filename = {output_path.name!r}
        self.stack_layout.addWidget(self.embedded)

        for i, menu in enumerate(self.menus):
            combo = QComboBox(self.container)
            combo.setFixedHeight(menu["height"])
            combo.setFixedWidth(menu["width"])
            combo.move(menu["x"], menu["y"])
            combo.raise_()

            combo.addItems(menu["items"])
            start = self.initial_index(menu["initialState"], combo.count())
            address = self.control_address(menu["controlPv"], start)
            if address is not None and address.startswith("loc://"):
                # Start where the variable starts, so the menu, its macros and
                # the variable agree before the channel's first value arrives.
                # (A PV's menu shows initialState until then.)
                init = re.search("[?&]init=([^&]*)", address)
                start = self.menu_index(init.group(1) if init else "0", combo.count(), start)
            combo.setCurrentIndex(start)
            combo.currentIndexChanged.connect(
                lambda selected_index, combo_index=i: self.menu_selected(combo_index, selected_index)
            )

            self.muxes.append(combo)
            self.macro_mappings.append(menu["macros"])
            self.control_addresses.append(address)
            self.control_writers.append(None if address is None else ControlPvWriter())
            self.control_connections.append(False)

        self.destroyed.connect(partial(disconnect_channels, self.control_channels))

        layout = QVBoxLayout(self)
        layout.addWidget(self.container)

        # Start every menu at its initial item, then load once
        for j, combo in enumerate(self.muxes):
            self.set_menu_macros(j, combo.currentIndex())
        self.load()

    def expand(self, text):
        # The screen's macros, which the converter writes as ${{name}}; unknown ones stay.
        macros = self.macros()
        return re.sub(
            "[$][{{(]([A-Za-z0-9_]+)[}})]",
            lambda m: str(macros.get(m.group(1), m.group(0))),
            text,
        )

    def initial_index(self, state, count):
        # EDM's initialState: the index of the first item shown. It may use
        # the screen's macros ("${{initDev}}") and is read like strtol, so
        # "3+1" is 3; anything unusable starts at 0.
        match = re.match("[ ]*(-?[0-9]+)", self.expand(state))
        index = int(match.group(1)) if match else 0
        return index if 0 <= index < count else 0

    def control_address(self, address, start):
        # With a controlPv, EDM ignores initialState: the menu shows the PV's
        # value. A loc:// variable nothing on the screen configures has no
        # value in EDM until another screen defines it; here the menu
        # declares it as an int starting at initialState, the only start
        # the screen gives.
        if address is None:
            return None
        address = self.expand(address)
        if address.startswith("loc://") and "?" not in address:
            address += "?type=int&init=" + str(start)
        return address

    def menu_index(self, value, count, default=None):
        # EDM reads the controlPv as an integer (a string like strtol, so
        # "1.5" is 1 and "OFF" is 0) and clamps it to the menu's items.
        if isinstance(value, str):
            match = re.match("[ ]*([-+]?[0-9]+)", value)
            value = match.group(1) if match else 0
        try:
            index = int(value)
        except (TypeError, ValueError, OverflowError):
            return default
        if count < 1:
            return default
        return min(max(index, 0), count - 1)

    def showEvent(self, event):
        super().showEvent(event)
        # The menus connect once the embedded .ui has loaded, which it does
        # when first shown. Its widgets then configure their loc:// variables
        # as they would on their own, and a variable only a menu configures
        # reaches every rule already listening to it: PyDM's rules skip a
        # value that arrives before the channel reports it is connected.
        if not self.controls_connected:
            self.controls_connected = True
            for i, address in enumerate(self.control_addresses):
                if address is not None:
                    self.connect_control(i, address)

    def connect_control(self, combo_index, address):
        channel = PyDMChannel(
            address=address,
            connection_slot=partial(self.control_connected, combo_index),
            value_slot=partial(self.control_changed, combo_index),
            value_signal=self.control_writers[combo_index].send_value_signal,
        )
        channel.connect()
        self.control_channels.append(channel)

    def control_connected(self, combo_index, connected):
        # Having a connection slot matters more than its use: when a listener
        # with one joins a loc:// variable, PyDM tells every listener it is
        # connected, which the rules of the widget that created it need.
        self.control_connections[combo_index] = connected

    def menu_selected(self, combo_index, selected_index):
        writer = self.control_writers[combo_index]
        if writer is None:
            self.update_display(combo_index, selected_index)
        elif not self.showing_control_value:
            # As in EDM, choosing an item only writes its index to the
            # controlPv; the menu and its macros follow the value it reports.
            writer.send_value_signal.emit(selected_index)

    def control_changed(self, combo_index, value):
        combo = self.muxes[combo_index]
        index = self.menu_index(value, combo.count())
        if index is None:
            return
        # Show the PV's item without writing it back.
        self.showing_control_value = True
        try:
            combo.setCurrentIndex(index)
        finally:
            self.showing_control_value = False
        self.update_display(combo_index, index)

    def set_menu_macros(self, combo_index, selected_index):
        for macro_name, value_list in self.macro_mappings[combo_index]:
            self.current_macros[macro_name] = value_list[selected_index]

    def update_display(self, combo_index, selected_index):
        self.set_menu_macros(combo_index, selected_index)
        self.load()

    def load(self):
        old = self.embedded.embedded_widget
        reloading = old is not None and json.dumps(self.current_macros) != self.embedded.macros
        if reloading:
            # PyDM keeps a loc:// variable, with its first init, while anything
            # listens to it, and connects the new display before releasing the
            # old one (slaclab/pydm#1354). Release the old display's channels
            # and rules first so variables initialised from these macros are
            # rebuilt with the new values.
            self.embedded.disconnect()
            unregister_widget_rules(old)
            QCoreApplication.sendPostedEvents()
        # Posted events can include a controlPv value that changes the macros.
        self.embedded.set_macros_and_filename(self.embedded.filename, json.dumps(self.current_macros))
        if reloading and self.controls_connected and self.embedded.embedded_widget is not old:
            # The menus' loc:// variables outlived the reload, so the new .ui's
            # rules joined them with no fresh value: PyDM sends a joining
            # listener the value before marking it connected, and its rules
            # skip a value from an unconnected channel. Join once more so the
            # value reaches them. (While the screen is hidden the .ui reloads
            # only when shown, which this does not cover.)
            for address in self.control_addresses:
                if address is not None and address.startswith("loc://"):
                    channel = PyDMChannel(address=address, connection_slot=lambda connected: None)
                    channel.connect()
                    channel.disconnect()
"""

    with open(file_path, "w") as f:
        f.write(code)

    logger.info(f"Generated: {file_path}")


def menu_item_count(obj: EDMObject) -> int:
    """A menu mux's number of items: numItems, or failing that the length of
    symbolTag, or of its longest value array."""
    num_items = obj.properties.get("numItems")
    if isinstance(num_items, str) and num_items.strip().isdecimal():
        return int(num_items)
    tags = edm_array(obj.properties.get("symbolTag"))
    if tags:
        return len(tags)
    return max(
        (len(edm_array(value)) for key, value in obj.properties.items() if re.fullmatch("value[0-9]+", key)),
        default=0,
    )


def menu_macros(obj: EDMObject, count: int) -> list[tuple[str, list[str]]]:
    """A menu mux's (macro, value per item) pairs, one per symbol{i}. EDM
    leaves trailing empty strings out of value{i}, and leaves value{i} out
    altogether when all of its values are empty, so pad each to count."""
    if count == 0:
        # An empty menu has no item selected (index -1) to take values from.
        return []
    symbols = sorted(
        (key for key in obj.properties if re.fullmatch("symbol[0-9]+", key)),
        key=lambda key: int(key.removeprefix("symbol")),
    )
    macros = []
    for key in symbols:
        names = edm_array(obj.properties[key])
        if names and names[0]:
            values = edm_array(obj.properties.get("value" + key.removeprefix("symbol")))
            macros.append((names[0], padded(values, count)))
    return macros


def menu_items(obj: EDMObject, count: int, macros: list[tuple[str, list[str]]]) -> list[str]:
    """A menu mux's item labels. Without symbolTag EDM shows blank items, so
    label each item by its first macro's value instead."""
    tags = edm_array(obj.properties.get("symbolTag"))
    if tags:
        return padded(tags, count)
    return list(macros[0][1]) if macros else [""] * count


def control_pv(obj: EDMObject, loc_declarations: dict[str, str]) -> str | None:
    """The address a menu mux writes its selected index to, or None without a controlPv.

    The parser has already turned a LOC\\ controlPv into a loc:// address. The
    screen connects its menus after the embedded .ui, whose widgets therefore
    configure a variable they declare, so the menu takes that declaration and
    keeps its own only when nothing else on the screen configures the
    variable. (EDM connects menu muxes first, so there a menu's own
    configuration wins; screens that configure a variable differently in two
    places are rare.)
    """
    address = obj.properties.get("controlPv")
    if not isinstance(address, str) or not address.strip() or address.strip().startswith("#"):
        return None
    address = address.strip()
    if address.startswith(("LOC\\", "CALC\\")):
        logger.warning(f"Menu mux controlPv {address} was not translated; the menu will not use it")
        return None
    if address.startswith("loc://"):
        return loc_declarations.get(address.split("?", 1)[0], address)
    return address


def edm_array(value) -> list[str]:
    """An EDM array property as a list: the parser gives a list for a
    { ... } block and a str for a single value."""
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, str) else []


def padded(values: list[str], count: int) -> list[str]:
    """values cut to count entries, or padded to it with the trailing empty
    strings EDM leaves out."""
    return values[:count] + [""] * (count - len(values))
