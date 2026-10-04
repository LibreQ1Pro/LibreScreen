"""Faults found in use: values that stayed "---", positions of axes that are not homed, a message lost on a page that is shown again."""
import unittest
import unittest.mock

from librescreen import state as g
from librescreen.pages import file_list, move, printing, refresh
from support import PortRecorder


class ScreenFixesTest(PortRecorder):
    def test_the_position_of_an_axis_that_is_not_homed_is_not_shown(self):
        g.klippy.homed_axes = "xy"
        g.klippy.x_position, g.klippy.y_position, g.klippy.z_position = 12.5, 30.0, 0.0
        move.move_page()
        sent = self.sent()
        self.assertIn('x_pos.txt="12.5"', " ".join(sent).replace("12.50", "12.5"))
        self.assertIn('z_pos.txt="%s"' % move.UNKNOWN_POSITION, sent)

    def test_nothing_is_homed_yet(self):
        g.klippy.homed_axes = ""
        move.move_page()
        self.assertEqual([c for c in self.sent() if c.endswith('_pos.txt="%s"' % move.UNKNOWN_POSITION)], ['x_pos.txt="---.-"', 'y_pos.txt="---.-"', 'z_pos.txt="---.-"'])

    def test_speed_and_flow_are_written_again_on_a_page_that_is_shown_anew(self):
        g.klippy.gcode_move_speed_factor, g.klippy.gcode_move_extrude_factor = 1.0, 0.95
        printing.printing_second_page()
        self.assertIn('speed_val.txt="100"', self.sent())
        self.assertIn('flow_val.txt="95"', self.sent())
        self.commands.clear()
        printing.printing_second_page()                                # nothing changed: nothing is sent
        self.assertNotIn('speed_val.txt="100"', self.sent())
        self.port.page("36")                                           # a page shown anew forgets its values
        self.commands.clear()
        printing.printing_second_page()
        self.assertIn('speed_val.txt="100"', self.sent())

    def test_the_failure_message_is_written_again_when_the_page_is_reopened(self):
        g.klippy.webhooks_state_message = "Printer is shutdown"
        refresh.show_failure_message()
        self.assertTrue(any(c.startswith("err_msg.txt=") for c in self.sent()))
        self.commands.clear()
        self.port.page("77")                                           # the page is opened again: its text is gone
        self.commands.clear()
        refresh.show_failure_message()
        self.assertTrue(any(c.startswith("err_msg.txt=") for c in self.sent()))


class ListPictureTest(PortRecorder):
    def test_the_list_thumbnail_is_a_multiple_of_16_and_420(self):
        # the screen draws the rows of a JPEG whose width is not a multiple of 16 sheared (a staircase)
        import io
        from PIL import Image
        from librescreen.screen import thumbnail
        png = io.BytesIO()
        Image.new("RGB", (160, 160), (200, 50, 50)).save(png, "PNG")
        thumb = thumbnail.Thumbnail("PNG", 160, 160, png.getvalue())
        with unittest.mock.patch.object(thumbnail, "get_thumbnails", return_value=[thumb]):
            data = thumbnail.jpeg("any.gcode", thumbnail.LIST_SIZE)
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (thumbnail.LIST_SIZE, thumbnail.LIST_SIZE))
        self.assertEqual(thumbnail.LIST_SIZE % 16, 0)
        from PIL import JpegImagePlugin
        self.assertEqual(JpegImagePlugin.get_sampling(image), 0)        # 4:4:4


if __name__ == "__main__":
    unittest.main()


class ShownNameTest(unittest.TestCase):
    def test_gcode_is_not_shown(self):
        self.assertEqual(file_list.shown_name("Benchy_PLA.gcode"), "Benchy_PLA")
        self.assertEqual(file_list.shown_name("cube.GCODE"), "cube")
        self.assertEqual(file_list.shown_name("models"), "models")
        self.assertEqual(file_list.shown_name(".gcode"), ".gcode")
        self.assertEqual(file_list.shown_name("part.gco"), "part.gco")


class WrapTextTest(unittest.TestCase):
    def test_words_are_not_cut(self):
        from librescreen.screen import text
        message = "Shutdown due to webhooks request. Use the FIRMWARE_RESTART command to reset the firmware."
        wrapped = text.wrap_text(message, 190, 6)
        lines = wrapped.split("\\r")
        for line in lines:
            self.assertLessEqual(text.width(line), 190, line)
        self.assertEqual(" ".join(lines), message)          # no word was cut, nothing lost

    def test_a_new_line_of_the_message_is_kept(self):
        from librescreen.screen import text
        self.assertEqual(text.wrap_text("one\ntwo", 190, 6), "one\\rtwo")

    def test_a_word_wider_than_the_line_is_cut_and_the_rest_ends_with_an_ellipsis(self):
        from librescreen.screen import text
        wrapped = text.wrap_text("w" * 60, 100, 6).split("\\r")
        self.assertGreater(len(wrapped), 1)
        self.assertTrue(all(text.width(line) <= 100 for line in wrapped))
        many = text.wrap_text("word " * 100, 100, 3).split("\\r")
        self.assertEqual(len(many), 3)
        self.assertTrue(many[-1].endswith("…"))

    def test_text_that_fits_is_unchanged(self):
        from librescreen.screen import text
        self.assertEqual(text.wrap_text("Printer is ready", 190, 6), "Printer is ready")
