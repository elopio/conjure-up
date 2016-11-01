""" Application Architecture / Machine Placement View

"""
import logging

import q
from urwid import Columns, Filler, Frame, Pile, Text, WidgetWrap

from conjureup.app_config import app
from conjureup.ui.widgets.juju_machines_list import JujuMachinesList
from conjureup.ui.views.machine_pin_view import MachinePinView

from ubuntui.ev import EventLoop
from ubuntui.utils import Color, Padding
from ubuntui.widgets.buttons import menu_btn
from ubuntui.widgets.hr import HR

log = logging.getLogger('conjure')


class AppArchitectureView(WidgetWrap):

    def __init__(self, application, controller):
        """
        application: a Service instance representing a juju application

        controller: a DeployGUIController instance
        """
        self.controller = controller
        self.application = application

        self.header = "Architecture"
        self._placements = []

        self._machines = app.metadata_controller.bundle.machines.copy()

        self.alarm = None
        self.widgets = self.build_widgets()
        self.description_w = Text("")
        self.buttons_selected = False
        self.frame = Frame(body=self.build_widgets(),
                           footer=self.build_footer())
        super().__init__(self.frame)
        self.update()

    def selectable(self):
        return True

    def keypress(self, size, key):
        # handle keypress first, then get new focus widget
        rv = super().keypress(size, key)
        if key in ['tab', 'shift tab']:
            self._swap_focus()
        return rv

    def _swap_focus(self):
        if not self.buttons_selected:
            self.buttons_selected = True
            self.frame.focus_position = 'footer'
            self.buttons.focus_position = 3
        else:
            self.buttons_selected = False
            self.frame.focus_position = 'body'

    def build_widgets(self):
        ws = [Text("Choose where to place {} unit{} of {}".format(
            self.application.num_units,
            "" if self.application.num_units == 1 else "s",
            self.application.service_name))]

        controller_is_maas = self.controller.cloud_type == 'maas'
        self.machines_list = JujuMachinesList(self.application,
                                              self._machines,
                                              self.do_select,
                                              self.do_unselect,
                                              self.add_machine,
                                              self.remove_machine,
                                              self,
                                              show_filter_box=True,
                                              show_pins=controller_is_maas)
        ws.append(self.machines_list)

        self.pile = Pile(ws)
        return Padding.center_90(Filler(self.pile, valign="top"))

    def build_footer(self):
        cancel = menu_btn(on_press=self.do_cancel,
                          label="\n  BACK\n")
        self.apply_button = menu_btn(on_press=self.do_commit,
                                     label="\n APPLY\n")
        self.buttons = Columns([
            ('fixed', 2, Text("")),
            ('fixed', 13, Color.menu_button(
                cancel,
                focus_map='button_primary focus')),
            Text(""),
            ('fixed', 20, Color.menu_button(
                self.apply_button,
                focus_map='button_primary focus')),
            ('fixed', 2, Text(""))
        ])

        footer = Pile([
            HR(top=0),
            Padding.center_90(self.description_w),
            Padding.line_break(""),
            Color.frame_footer(Pile([
                Padding.line_break(""),
                self.buttons]))
        ])

        return footer

    def update_now(self, *args):
        if len(self._placements) == self.application.num_units:
            self.machines_list.all_assigned = True
        else:
            self.machines_list.all_assigned = False
        self.machines_list.update()

    def update(self, *args):
        self.update_now()
        self.alarm = EventLoop.set_alarm_in(1, self.update)

    def do_select(self, machine, assignment_type):
        self._placements.append((machine,
                                 assignment_type))
        self.update_now()

    def do_unselect(self, machine):
        self._placements = [(m, at) for (m, at) in self._placements
                            if m != machine]
        self.update_now()

    def get_all_placements(self, machine_id):
        """merge committed placements of other apps with temporary placements
        of this app
        """
        all_placements = [(a, at) for (a, at)
                          in self.controller.placements[machine_id]
                          if a != self.application]
        return all_placements + self._placements

    def add_machine(self):
        md = dict(series=app.metadata_controller.bundle.series)
        self._machines[str(len(self._machines))] = md

    def remove_machine(self):
        raise Exception("TODO")

    def get_pin(self, juju_machine_id):
        q.q(juju_machine_id)
        return 1

    def show_pin_chooser(self, juju_machine_id):
        app.ui.set_header("Pin Machine {}".format(juju_machine_id))
        mpv = MachinePinView(juju_machine_id, self)
        app.ui.set_body(mpv)

    def handle_sub_view_done(self):
        app.ui.set_header(self.header)
        self.update_now()
        app.ui.set_body(self)

    def set_pin(self, juju_machine_id, maas_machine_id):
        q.q(juju_machine_id, maas_machine_id)

    def unset_pin(self, juju_machine_id):
        q.q(juju_machine_id)

    def commit_machine_pin(self):
        q.q("commit")

    def do_cancel(self, sender):
        self.controller.handle_sub_view_done()
        if self.alarm:
            EventLoop.remove_alarm(self.alarm)

    def do_commit(self, sender):
        "Commit changes to placements and constraints"
        self.controller.clear_placements(self.application)
        for machine, atype in self._placements:
            self.controller.add_placement(self.application, machine, atype)

        self.controller.handle_sub_view_done()
        if self.alarm:
            EventLoop.remove_alarm(self.alarm)
