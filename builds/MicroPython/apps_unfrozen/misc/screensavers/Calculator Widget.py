"""Native-size Calculate widget with textbook input and no history."""
WIDGET_NATIVE=True
_owner=None

def start(vm):
    global _owner
    from engtools.calculator.app import CalculatorView
    _owner=CalculatorView(compact=True)
    return _owner.start(vm)

def run(vm):
    if _owner is not None: _owner.run(vm)

def stop(vm):
    global _owner
    if _owner is not None: _owner.stop(vm)
    _owner=None
