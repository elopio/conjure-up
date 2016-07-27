from ubuntui.utils import Padding
from urwid import (WidgetWrap, Text, Filler, Pile, Columns)
import random


class BootstrapWaitView(WidgetWrap):

    load_attributes = [('pending_icon', "\u2581"),
                       ('pending_icon', "\u2582"),
                       ('pending_icon', "\u2583"),
                       ('pending_icon', "\u2584"),
                       ('pending_icon', "\u2585"),
                       ('pending_icon', "\u2586"),
                       ('pending_icon', "\u2587"),
                       ('pending_icon', "\u2588")]

    def __init__(self, app, message):
        self.message = Text(message, align="center")
        self.app = app
        self.loading_boxes = [Text(x) for x in self.load_attributes]
        super().__init__(self._build_node_waiting())

    def redraw_kitt(self):
        """ Redraws the KITT bar
        """
        random.shuffle(self.load_attributes)
        for i in self.loading_boxes:
            i.set_text(
                self.load_attributes[random.randrange(
                    len(self.load_attributes))])
        self.log_txt.set_text("".join(self.app.bootstrap.output[-10:]))

    def _build_node_waiting(self):
        """ creates a loading screen if nodes do not exist yet """
        text = [Padding.line_break(""),
                self.message,
                Padding.line_break("")]

        _boxes = []
        _boxes.append(('weight', 1, Text('')))
        for i in self.loading_boxes:
            _boxes.append(('pack', i))
        _boxes.append(('weight', 1, Text('')))
        _boxes = Columns(_boxes)

        self.log_txt = Text("")

        return Filler(Pile(text + [_boxes, Padding.center_50(self.log_txt)]),
                      valign="middle")
