##
# Copyright (c) 2015-2017 Intel Inc. All rights reserved.
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
##

import lldb

class NullPyObjectPtr(RuntimeError):
    pass

class PyObjectPtr(object):
    """
    Class wrapping a value that's either a (PyObject *) within the
    inferior process, or some subclass pointer e.g. (PyBytesObject *)

    There will be a subclass for every refined PyObject type that we
    care about

    Note that at every stage the underlying pointer could be nullptr,
    point to corrupt data, etc; this is the debugger, after all.
    """
    _typename = 'PyObject'

    def __init__(self, sbval):
        self._SBValue = sbval;

    def field(self, name):
        """
        Get the lldb SBValue for the given field within the PyObject,
        coping with some python 2 versus python 3 differences.

        Various types are defined using the "PyObject_HEAD" and
        "PyObject_VAR_HEAD" macros.

        In Python 2, these are defined so that "ob_type" and (for a var
        object) "ob_size" are fields fo the type in question.

        In Python 3, this is defined as an embedded PyVarObject type thus:
            PyVarObject ob_base;

        So that the "ob_size" field is located inside the "ob_base" field,
        and the "ob_type" is most easily accessed by casting back to a
        (PyObject *).
        """
        if self.is_null():
            raise NullPyObjectPtr(self)

        return self._SBValue.GetChildMemberWithName(name)

    def pyop_field(self, name):
        """
        Get a PyObjectPtr for the given PyObject *field within this
        PyObject, coping with some python 2 versus 3 differences.
        """
        return NotImplemented

    def write_field_repr(self, name, out, visited):
        """
        Extract the PyObject *field named "name", and write its representation
        to file-like object "out"
        """
        return NotImplemented

    def get_truncated_repr(self, maxlen):
        """
        Get a repr-link string for the data, but truncate it at "maxlen" bytes
        (ending the object graph traversal as soon as you do)
        """
        return NotImplemented

    def type(self):
        return PyTypeObjectPtr(self.field('ob_type'))

    def is_null(self):
        return 0 == long(self._SBValue.GetValueAsUnsigned())

    def is_optimized_out(self):
        return NotImplemented

    def safe_tp_name(self):
        return NotImplemented

    def proxyval(self, visited):
        return NotImplemented

    def write_repr(self, out, visited):
        return NotImplemented

    @classmethod
    def subclass_from_type(cls, t):
        return NotImplemented

    @classmethod
    def from_pyobject_ptr(cls, sbval):
        """
        Try to locate the appropritate drived class dynamically, and cast
        the pointer accordingly.
        """
        return NotImplemented

    @classmethod
    def get_lldb_type(cls):
        return NotImplemented

    def as_address(self):
        return long(self._SBValue)

def Evaluate_PyObject_AsUTF8(fr, obj):
    return fr.EvaluateExpression('PyUnicode_AsUTF8('+obj+')')

def Evaluate_LineNo(fr, obj):
    return fr.EvaluateExpression('PyFrame_GetLineNumber('+obj+')')

def gist_extr(s):
    return s[s.find('"') +1: s.rfind('"')]

def is_evalframeex(frame):
    return frame.GetFunctionName() == 'PyEval_EvalFrameEx'

def py3bt(debugger=None, command=None, result=None, dict=None, thread=None):
    """
    An lldb command that prints a Python call back trace for the specified
    thread or the currently selected thread.

    @param debugger: debugger to use
    @type debugger: L{lldb.SBDebugger}
    @param command: ignored
    @type command: ignored
    @param result: ignored
    @type result: ignored
    @param dict: ignored
    @type dict: ignored
    @param thread: the specific thread to target
    @type thread: L{lldb.SBThread}
    """

    if debugger is None:
        debugger = lldb.debugger
    target = debugger.GetSelectedTarget()

    if not isinstance(thread, lldb.SBThread):
        thread = target.GetProcess().GetSelectedThread()

    num_frames = thread.GetNumFrames()

    for i in range(num_frames - 1):
        fr = thread.GetFrameAtIndex(i)
        if is_evalframeex(fr):
            f = fr.GetValueForVariablePath("f")
            f = PyObjectPtr(f)
            f_code = PyObjectPtr(f.field('f_code'))
            filename = f_code.field('co_filename').GetValue()
            name = f_code.field('co_name').GetValue()
            lineno = Evaluate_LineNo(fr, "f").GetValue();

            print("frame #{}: {} - {}:{}".format(
                fr.GetFrameID(),
                filename if filename else ".",
                name if name else ".",
                lineno if lineno else ".",
            ))

CMDS = [("py3-bt", "py3bt")]


def __lldb_init_module(debugger, dict):
    """
    Register each command with lldb so they are available directly within lldb as
    well as within its Python script shell.

    @param debugger: debugger to use
    @type debugger: L{lldb.SBDebugger}
    @param dict: ignored
    @type dict: ignored
    """
    for cmd in CMDS:
        debugger.HandleCommand(
            "command script add -f lldb_utils.{func} {cmd}".format(cmd=cmd[0],
            func=cmd[1])
        )