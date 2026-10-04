"""The looks the host gives its widgets (librescreen/screen/faces.py): every ``face(widget, state)`` it asks for exists."""
import ast
import os
import unittest

from librescreen.screen.faces import FACES

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "librescreen")


def literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def names(node):
    """The widget names of a tuple / list of string literals, or a single name."""
    if isinstance(node, (ast.Tuple, ast.List)):
        found = [literal(e) for e in node.elts]
        return found if all(found) else []
    return [literal(node)] if literal(node) else []


def requests():
    """(file, line, widget, state) of every face the code asks for with literals."""
    found = []
    for folder, _, files in os.walk(ROOT):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for call in ast.walk(tree):
                if not isinstance(call, ast.Call):
                    continue
                func = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
                args = call.args
                if func == "face" and len(args) == 2 and literal(args[1]):
                    found += [(path, call.lineno, w, literal(args[1])) for w in names(args[0])]
                elif func == "face_group" and args:
                    states = [literal(a) for a in args[2:4]] or ["on", "off"]
                    states += ["on", "off"][len(states):]
                    found += [(path, call.lineno, w, s) for w in names(args[0]) for s in states]
                elif func == "two_state_button" and args:
                    found += [(path, call.lineno, w, s) for w in names(args[0]) for s in ("on", "off")]
    return found


class FacesTest(unittest.TestCase):
    def test_every_look_has_a_released_tile(self):
        for widget, states in FACES.items():
            for state, (released, pressed) in states.items():
                self.assertTrue(released.isdigit(), (widget, state))
                self.assertTrue(pressed is None or pressed.isdigit(), (widget, state))

    def test_the_code_asks_for_looks_that_exist(self):
        asked = requests()
        self.assertGreater(len(asked), 20)
        for path, line, widget, state in asked:
            self.assertIn(state, FACES.get(widget, {}), "%s:%d face(%r, %r)" % (os.path.relpath(path, ROOT), line, widget, state))


if __name__ == "__main__":
    unittest.main()
