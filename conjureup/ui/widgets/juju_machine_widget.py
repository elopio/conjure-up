import q
# Copyright 2016 Canonical, Ltd.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import defaultdict
import logging

from urwid import (AttrMap, Columns, connect_signal, Divider, Edit,
                   Pile, Text, WidgetWrap)

from bundleplacer.assignmenttype import AssignmentType, atype_to_label

from conjureup import juju
from ubuntui.widgets.buttons import PlainButton


log = logging.getLogger('bundleplacer')


class JujuMachineWidget(WidgetWrap):

    """A widget displaying a machine and action buttons.

    machine_id = juju id of the machine

    md = the machine dict

    application - the current application for which machines are being shown

    select_cb - a function that takes a machine and assignmenttype to
    perform the button action

    unselect_cb - a function that takes a machine and removes
    assignments for the machine

    controller - a controller object that provides show_pin_chooser

    show_assignments - display info about which charms are assigned
    and what assignment type (LXC, KVM, etc) they have.

    show_pin - show whether a machine has been pinned to a maas machine.
    """

    def __init__(self, machine_id, md, application, select_cb, unselect_cb,
                 controller, show_assignments=True, show_pin=False):
        self.machine_id = machine_id
        self.md = md
        self.application = application
        self.is_selected = False
        self.select_cb = select_cb
        self.unselect_cb = unselect_cb
        self.controller = controller
        self.show_assignments = show_assignments
        self.show_pin = show_pin
        self.all_assigned = False

        w = self.build_widgets()
        super().__init__(w)
        self.update()

    def selectable(self):
        return True

    def __repr__(self):
        return "jujumachinewidget #" + str(self.machine_id)

    def build_widgets(self):

        self.action_button_cols = Columns([])
        self.action_buttons = []
        self.unselected_widgets = self.build_unselected_widgets()
        self.pile = Pile([self.unselected_widgets])
        return self.pile

    def build_unselected_widgets(self):
        cdict = juju.constraints_to_dict(self.md.get('constraints', ''))

        self.machine_id_button = PlainButton('{:20s}'.format(self.machine_id),
                                             self.show_pin_chooser)
        self.cores_field = Edit('', cdict.get('cores', ''))
        connect_signal(self.cores_field, 'change', self.handle_cores_changed)
        self.mem_field = Edit('', cdict.get('mem', ''))
        connect_signal(self.mem_field, 'change', self.handle_mem_changed)
        self.disk_field = Edit('', cdict.get('root-disk', ''))
        connect_signal(self.disk_field, 'change', self.handle_disk_changed)

        assignments = []

        mps = self.controller.get_all_placements(self.machine_id)
        if len(mps) > 0:
            if self.show_assignments:
                ad = defaultdict(list)
                for application, atype in mps:
                    ad[atype].append(application)
                astr = " ".join(["{}{}".format(atype_to_label(atype),
                                               ",".join([a.service_name
                                                         for a in al]))
                                 for atype, al in ad.items()])
                assignments.append(astr)
            action = self.do_remove
            label = "Remove"
        else:
            if self.show_assignments:
                assignments.append("-")
            action = self.do_select
            label = "Select"

        self.select_button = PlainButton(label, action)
        cols = [self.machine_id_button, self.cores_field,
                self.mem_field, self.disk_field]
        cols += [Text(s) for s in assignments]

        current_assignments = [a for a, _ in mps if a == self.application]
        if self.all_assigned and len(current_assignments) == 0:
            cols.append(Text(""))
        else:
            cols += [AttrMap(self.select_button, 'text',
                             'button_secondary focus')]

        return Columns(cols)

    def update(self):
        self.update_action_buttons()

        if self.is_selected:
            self.update_selected()
        else:
            self.update_unselected()

    def update_selected(self):
        cn = self.application.service_name
        msg = Text("  Add {} to machine #{}:".format(cn,
                                                     self.machine_id))
        self.pile.contents = [(msg, self.pile.options()),
                              (self.action_button_cols,
                               self.pile.options()),
                              (Divider(), self.pile.options())]

    def update_unselected(self):
        if self.show_pin:
            pinned_machine = self.controller.get_pin(self.machine_id)

            if pinned_machine:
                pin_label = "({})".format(pinned_machine)
            else:
                pin_label = ""
            self.machine_id_button.set_label('{:20s} {}'.format(self.machine_id,
                                                              pin_label))
        else:
            self.machine_id_button.set_label('{:20s}'.format(self.machine_id))

        self.pile.contents = [(self.unselected_widgets, self.pile.options()),
                              (Divider(), self.pile.options())]

    def update_action_buttons(self):

        all_actions = [(AssignmentType.BareMetal,
                        'Add as Bare Metal',
                        self.select_baremetal),
                       (AssignmentType.LXD,
                        'Add as LXD',
                        self.select_lxd),
                       (AssignmentType.KVM,
                        'Add as KVM',
                        self.select_kvm)]

        sc = self.application
        if sc:
            allowed_set = set(sc.allowed_assignment_types)
            allowed_types = set([atype for atype, _, _ in all_actions])
            allowed_types = allowed_types.intersection(allowed_set)
        else:
            allowed_types = set()

        # + 1 for the cancel button:
        if len(self.action_buttons) == len(allowed_types) + 1:
            return

        self.action_buttons = [AttrMap(PlainButton(label,
                                                   on_press=func),
                                       'button_secondary',
                                       'button_secondary focus')
                               for atype, label, func in all_actions
                               if atype in allowed_types]
        self.action_buttons.append(
            AttrMap(PlainButton("Cancel",
                                on_press=self.do_cancel),
                    'button_secondary',
                    'button_secondary focus'))

        opts = self.action_button_cols.options()
        self.action_button_cols.contents = [(b, opts) for b in
                                            self.action_buttons]

    def do_select(self, sender):
        self.is_selected = True
        self.update()
        self.pile.focus_position = 1
        self.action_button_cols.focus_position = 0

    def do_remove(self, sender):
        self.unselect_cb(self.machine_id)

    def do_cancel(self, sender):
        self.is_selected = False
        self.update()
        self.pile.focus_position = 0

    def _do_select_assignment(self, atype):
        self.select_cb(self.machine_id, atype)
        self.pile.focus_position = 0
        self.is_selected = False
        self.update()

    def select_baremetal(self, sender):
        self._do_select_assignment(AssignmentType.BareMetal)

    def select_lxd(self, sender):
        self._do_select_assignment(AssignmentType.LXD)

    def select_kvm(self, sender):
        self._do_select_assignment(AssignmentType.KVM)

    def handle_cores_changed(self, sender, val):
        q.q(val)

    def handle_mem_changed(self, sender, val):
        q.q(val)

    def handle_disk_changed(self, sender, val):
        q.q(val)

    def show_pin_chooser(self, sender):
        self.controller.show_pin_chooser(self.machine_id)
