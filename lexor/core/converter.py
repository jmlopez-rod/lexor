"""
Provides the |Converter| object which defines the basic mechanism for
converting the objects defined in :mod:`lexor.core.elements`. This
involves using objects derived from the abstract class
|NodeConverter|.

There are a couple of functions that have been written to be used
inside python embeddings. These are:

- :func:`get_converter_namespace`
- :func:`get_lexor_namespace`
- :func:`get_current_node` equivalent to ``__NODE__``
- :func:`echo`
- :func:`include`
- :func:`import_module`

When writing python embeddings there are several special variables
that can be used, one of them as mentioned above is ``__NODE__``
which has the returned value of the function
:func:`get_current_node`. The other two are ``__FILE__`` which takes
in the value of the path of the document which is executing the
python embedding and ``__DIR__`` which is equivalent to
``os.path.dirname(__FILE__)``.

.. |Converter| replace:: :class:`~.Converter`
.. |Parser| replace:: :class:`~lexor.core.parser.Parser`
.. |NodeConverter| replace:: :class:`~.Converter`
.. |Document| replace:: :class:`~lexor.core.elements.Document`
.. |DocFrag| replace:: :class:`~lexor.core.elements.DocumentFragment`
.. |Text| replace:: :class:`~lexor.core.elements.Text`
.. |PI| replace:: :class:`~lexor.core.elements.ProcessingInstruction`

"""
import sys
import os.path as pth
import traceback
import lexor
from imp import load_source
from cStringIO import StringIO
from lexor.command import config, LexorError
from lexor.command.lang import get_style_module, map_explanations
LC = sys.modules['lexor.core']


def get_converter_namespace():
    """Many converters may be defined during the conversion of a
    document. In some cases we may need to save references to objects
    in documents. If this is the case, then call this function to
    obtain the namespace where you can save those references. """
    return get_converter_namespace.namespace
if not hasattr(get_converter_namespace, 'namespace'):
    get_converter_namespace.namespace = dict()


class NodeConverter(object):
    """A node converter is an object which determines if the node
    will be copied (default). To avoid copying the node simply
    declare::

        copy = False

    when deriving a node converter. Note that by default, the
    children of the node (if any) will be copied and assigned to the
    parent. To avoid copying the children then set::

        copy_children = False

    """
    restrict = 'E'
    directive = None
    template = None
    template_uri = None
    template_options = None
    _t_element = None
    priority = 0
    remove = False  # replaces copy
    replace = False
    transclude = True  # replaces copy_children
    terminal = False
    require = False

    def compile(self, t_node, info):
        pass

    def pre_link(self, node):
        pass

    def post_link(self, node):
        pass

    copy = True
    copy_children = True

    def __init__(self, converter):
        """A node converter needs to be initialized with a converter
        object. If this method is to be overloaded then make sure
        that it only accepts one parameter: `converter`. This method
        is used by |Converter| and it calls it with itself as the
        parameter. """
        self.converter = converter
        if self.directive is None:
            raise LexorError('missing directive name')

    @classmethod
    def start(cls, node):
        """This method gets called only if ``copy`` is set to True
        (default). By overloading this method you have access to the
        converter and the node. You can thus set extra variables in
        the converter or modify the node. **DO NOT** modify any of
        the parents of the node. If there is a need to modify any of
        parents of the node then set a variable in the converter to
        point to the node so that later on in the ``convert``
        function it can be modified. """
        return node

    @classmethod
    def end(cls, node):
        """This method gets called after all the children have been
        copied. Make sure to return the node or the node replacement.
        """
        return node

    def msg(self, code, node, arg=None, uri=None):
        """Send a message to the converter by providing one of the
        error codes defined in the style as well as the position
        where the error took place. The position has the form of a
        list containing the line and column number. Some error codes
        may provide arguments, this can be passed to `arg`. In case
        the error occurred somewhere not in the current document,
        perhaps in a string, then you may provide a new `uri` to
        denote the location."""
        self.converter.msg(self.__module__, code, node, arg, uri)


# pylint: disable=R0903
class BaseLog(object):
    """A simple class to provide messages to a converter. You must
    derive an object from this class in the module which will be
    issuing the messages. For instance::

        class Log(BaseLog):
            pass

    After that you can create a new object and use it in a module::

        log = Log(converter)

    where `converter` is a |Converter| provided to the module. Make
    sure that the module contains the objects ``MSG`` and
    ``MSG_EXPLANATION``."""

    def __init__(self, converter):
        self.converter = converter

    def msg(self, code, arg=None, uri=None):
        """Send a message to the converter. """
        self.converter.msg(self.__module__, code, None, arg, uri)


# The default of 7 attributes for class is too restrictive.
# pylint: disable=R0902
class Converter(object):
    """To see the languages available to the converter see the
    :mod:`lexor.command.lang` module. """

    def __init__(self, fromlang='xml', tolang='xml',
                 style='default', defaults=None):
        """Create a new converter by specifying the language and the
        style in which node objects will be written. """
        if defaults is None:
            defaults = dict()
        self._fromlang = fromlang
        self._tolang = tolang
        self._style = style
        self._nc = None
        self._node_converter = None
        self._convert_func = None
        self._reload = True
        self.style_module = None
        self.doc = list()
        self.log = list()
        self.defaults = defaults

    def __getitem__(self, name):
        """Return the specified |NodeConverter|. """
        return self._node_converter[name]

    @property
    def convert_from(self):
        """The language from which the converter will convert. """
        return self._fromlang

    @convert_from.setter
    def convert_from(self, value):
        """Setter function for convert_from. """
        self._fromlang = value
        self._reload = True

    @property
    def convert_to(self):
        """The language to which the converter will convert. """
        return self._tolang

    @convert_to.setter
    def convert_to(self, value):
        """Setter function for convert_to. """
        self._tolang = value
        self._reload = True

    @property
    def converting_style(self):
        """The converter style. """
        return self._style

    @converting_style.setter
    def converting_style(self, value):
        """Setter function for converting_style. """
        self._style = value
        self._reload = True

    def set(self, fromlang, tolang, style, defaults=None):
        """Sets the languages and styles in one call. """
        if defaults is not None:
            self.defaults = defaults
        self._style = style
        self._tolang = tolang
        self._fromlang = fromlang
        self._reload = True

    def match_info(self, fromlang, tolang, style, defaults=None):
        """Check to see if the converter main information matches."""
        match = True
        if defaults is not None:
            match = False
        elif fromlang not in [self._fromlang]:
            match = False
        elif tolang not in [self._tolang]:
            match = False
        elif style not in [self._style]:
            match = False
        return match

    @property
    def lexor_log(self):
        """The `lexorlog` document. See this document after each
        call to :meth:`convert` to see warnings and errors. """
        return self.log[-1]

    @property
    def document(self):
        """The parsed document. This is a |Document| or |DocFrag|
        created by the :meth:`convert` method. """
        return self.doc[-1]

    def pop(self):
        """Remove the last document and last log document and return
        them. """
        return self.doc.pop(), self.log.pop()

    def convert(self, doc, namespace=False):
        """Convert the |Document| or |DocFrag| doc. """
        if not isinstance(doc, (LC.Document, LC.DocumentFragment)):
            raise TypeError("The node is not a Document or DocumentFragment")
        if self._reload:
            self._set_node_converters(
                self._fromlang, self._tolang, self._style, self.defaults
            )
            self._reload = False
        self.log.append(LC.Document("lexor", "log"))
        self.log[-1].modules = dict()
        self.log[-1].explanation = dict()
        doccopy = self._compile_doc(doc)
        doccopy = self._link_doc(doccopy)
        self._convert(doc)
        if hasattr(self.style_module, 'convert'):
            self.style_module.convert(self, self.doc[-1])
        map_explanations(self.log[-1].modules, self.log[-1].explanation)
        if not namespace:
            del self.doc[-1].namespace
        self.doc[-1].lang = self._tolang
        self.doc[-1].style = 'default'
        return doccopy, self.log[-1]

    @staticmethod
    def remove_node(node):
        """Removes the node from the current document it is in.
        Returns the previous sibling is possible, otherwise it
        returns an empty |Text| node. """
        parent = node.parent
        index = node.index
        del node.parent[node.index]
        try:
            if index - 1 > -1:
                return parent[index-1]
            else:
                raise IndexError
        except IndexError:
            parent.append_child('')
        return parent[0]

    # pylint: disable=R0913
    def msg(self, mod_name, code, node, arg=None, uri=None):
        """Provide the name of module issuing the message, the `code`
        number, the node with the error, optional arguments and
        `uri`. This information gets stored in the converters log. """
        if uri is None:
            uri = self.doc[-1].uri_
        if arg is None:
            arg = ()
        wnode = LC.Void('msg')
        wnode['module'] = mod_name
        wnode['code'] = code
        wnode['node_id'] = id(node)
        wnode.node = node
        try:
            wnode['uri'] = node['uri']
            del node['uri']
        except (KeyError, TypeError):
            wnode['uri'] = uri
        wnode['arg'] = arg
        if mod_name not in self.log[-1].modules:
            self.log[-1].modules[mod_name] = sys.modules[mod_name]
        self.log[-1].append_child(wnode)

    def register(self, nc_class, override=False):
        """Add a node converter class. This function takes in a
        class object derived rom `Node Converter`.
        """
        node_c = nc_class(self)
        class_name = nc_class.__name__
        if not override:
            if class_name in self._node_converter:
                msg = 'overriding existing node converter class {0}'
                raise LexorError(msg.format(class_name))
            if node_c.directive in self._nc:
                msg = 'overriding existing node directive {0}'
                raise LexorError(msg.format(node_c.directive))
        self._node_converter[class_name] = node_c
        self._nc[node_c.directive] = node_c
        return node_c

    def _set_node_converters(self, fromlang, tolang, style, defaults=None):
        """Imports the correct module based on the languages and
        style. """
        self.style_module = get_style_module(
            'converter', fromlang, style, tolang
        )
        name = '%s-converter-%s-%s' % (fromlang, tolang, style)
        config.set_style_cfg(self, name, defaults)
        self._nc = dict()
        self._node_converter = dict()
        for nc_class in self.style_module.REPOSITORY:
            self.register(nc_class)

    def get_node_directives(self, node):
        """Examine the node and return a list of directives that can
        be applied to the node"""
        directives = []
        info = {
            'remove': []
        }
        name = node.name
        if name in self._nc and 'E' in self._nc[name].restrict:
            if self._nc[name].remove:
                info['remove'].append(name)
            priority = self._nc[name].priority
            directives.append((name, priority))
        if not isinstance(node, LC.Element):
            return directives, info
        for att in node.attributes:
            if att not in self._nc:
                continue
            node_c = self._nc[att]
            if 'A' not in node_c.restrict:
                continue
            if node_c.remove:
                info['remove'].append(att)
            priority = node_c.priority
            index = len(directives)
            while index > 0:
                if priority > directives[index-1][1]:
                    index -= 1
                else:
                    break
            directives.insert(index, (att, priority))
        # TODO: Handle classes
        return directives, info

    def _start(self, node):
        """Evaluate the start function of the node converter based
        on the name of the node. """
        if node.name in self._nc:
            return self._nc[node.name].start(node)
        return node

    def _end(self, node):
        """Evaluate the end function of the node converter based
        on the name of the node. """
        if node.name in self._nc:
            return self._nc[node.name].end(node)
        return node

    def _copy(self, node):
        """Return the copy attribute of the node converter. """
        if node.name in self._nc:
            return self._nc[node.name].copy
        return True

    def _template(self, node):
        """Return the template attribute of the node converter. """
        if node.name in self._nc:
            return self._nc[node.name].template
        return None

    def _copy_children(self, node):
        """Return the copy_children attribute of the node converter. """
        if node.name in self._nc:
            tmp = self._nc[node.name].copy_children
        else:
            tmp = True
        return tmp and node.child

    def _get_direction(self, crt):
        """Returns the direction in which the traversal should go. """
        if crt.child and self._copy_children(crt):
            return 'd'
        return 'r'

    @staticmethod
    def _get_link_direction(crt):
        return 'd' if crt.child else 'r'

    def _clone_node(self, crt):
        """Clones the node if the node converter assigned to the node
        has the copy property set to True. """
        if self._copy(crt):
            return crt.clone_node()
        return LC.Text('')

    def _compile_node(self, crt, crtcopy, down=False):
        directives, info = self.get_node_directives(crt)
        if not info['remove']:
            clone = crt.clone_node()
            if down:
                crtcopy.append_child(clone)
            else:
                crtcopy.parent.append_child(clone)
            crtcopy = clone
            direction = self._get_direction(crt)
        else:
            direction = 'r'
        if isinstance(crtcopy, LC.Element):
            crtcopy._directives = directives
            crtcopy._info = info
            crtcopy._t_node = dict()
        for directive, priority in directives:
            node_c = self._nc[directive]
            options = node_c.template_options or {}
            if not node_c._t_element:
                if node_c.template:
                    tdoc, tlog = lexor.lexor(
                        node_c.template, **options
                    )
                    node_c._t_element = tdoc
                else:
                    tdoc = None
            else:
                tdoc = node_c._t_element.clone_node(True)
            node_c.compile(tdoc, info)
            crtcopy._t_node[directive] = tdoc
        return crtcopy, direction

    def __pre_link_node(self, crt, crtcopy, down=False):
        if self._copy(crt):
            clone = crt.clone_node()
            if down:
                crtcopy.append_child(clone)
            else:
                crtcopy.parent.append_child(clone)
            crtcopy = clone
            crtcopy = self._start(crtcopy)
            direction = self._get_direction(crt)
        else:
            direction = 'r'
        return crtcopy, direction

    def _pre_link_node(self, crt):
        if not hasattr(crt, '_directives'):
            return
        for directive, priority in crt._directives:
            node_c = self._nc[directive]
            tmp = LC.DocumentFragment()
            while crt.child:
                tmp.append_child(crt.child[0])
            print 'TMP %r' % tmp
            print 'CHILDREN: %r, %r' % (node_c.transclude, tmp)
            t_node = crt._t_node[directive]
            crt.extend_children(t_node)
            if node_c.transclude:
                print '\n->TRANS: %r' % tmp
                # for c in tmp.child:
                #     print 'CHILD: %r' % c
                print '\n-CURRENT: %r' % crt
                crt.extend_children(tmp)
            node_c.pre_link(crt)

    def _post_link_node(self, crt):
        if not hasattr(crt, '_directives'):
            return
        for directive, priority in crt._directives:
            node_c = self._nc[directive]
            node_c.post_link(crt)

    def _compile_doc(self, doc):
        """Creates a copy of the document and calls the compile
        method on each of the template elements (if any).
        """
        crt = doc
        root = doc
        doccopy = doc.clone_node()
        doccopy.namespace = dict()
        # if hasattr(self.style_module, 'init_conversion'):
        #     self.style_module.init_conversion(self, doccopy)
        crtcopy = doccopy
        #crtcopy = self._start(crtcopy)
        direction = self._get_direction(crt)
        loop = direction == 'd'
        while loop:
            if direction is 'd':
                crt = crt.child[0]
                crtcopy, direction = self._compile_node(
                    crt, crtcopy, True
                )
            elif direction is 'r':
                if crt.next is None:
                    direction = 'u'
                else:
                    crt = crt.next
                    crtcopy, direction = self._compile_node(
                        crt, crtcopy
                    )
            else:  # direction is 'u'
                crtcopy = crtcopy.parent
                crtcopy.normalize()
                if crt.parent is root:
                    loop = False
                elif crt.parent.next is None:
                    crt = crt.parent
                    direction = 'u'
                else:
                    crt = crt.parent.next
                    crtcopy, direction = self._compile_node(
                        crt, crtcopy
                    )
        return doccopy

    def _link_doc(self, doccopy):
        """To be run after compiling the document.
        """
        crt = doccopy
        root = doccopy
        #self._pre_link_node(crt)
        direction = self._get_link_direction(crt)
        loop = direction == 'd'
        while loop:
            if direction is 'd':
                crt = crt.child[0]
                self._pre_link_node(crt)
                direction = self._get_link_direction(crt)
            elif direction is 'r':
                if crt.next is None:
                    direction = 'u'
                else:
                    crt = crt.next
                    self._pre_link_node(crt)
                    direction = self._get_link_direction(crt)
            else:  # direction is 'u'
                self._post_link_node(crt.parent)
                if crt.parent is root:
                    loop = False
                elif crt.parent.next is None:
                    crt = crt.parent
                    direction = 'u'
                else:
                    crt = crt.parent.next
                    self._pre_link_node(crt)
                    direction = self._get_link_direction(crt)
        return doccopy

    def _convert(self, doc):
        """Main convert function. """
        # A doc needs to be copied by default. You may prohibit
        # to copy the children, but there must be a document.
        crt = doc
        root = doc
        self.doc.append(doc.clone_node())
        self.doc[-1].namespace = dict()
        if hasattr(self.style_module, 'init_conversion'):
            self.style_module.init_conversion(self, self.doc[-1])
        crtcopy = self.doc[-1]
        crtcopy = self._start(crtcopy)
        direction = self._get_direction(crt)
        loop = direction == 'd'
        while loop:
            if direction is 'd':
                crt = crt.child[0]
                crtcopy, direction = self.__pre_link_node(
                    crt, crtcopy, True
                )
            elif direction is 'r':
                if crt.next is None:
                    direction = 'u'
                else:
                    crt = crt.next
                    crtcopy, direction = self.__pre_link_node(
                        crt, crtcopy
                    )
            else:  # direction is 'u'
                crtcopy = self._end(crtcopy.parent)
                crtcopy.normalize()
                if crt.parent is root:
                    loop = False
                elif crt.parent.next is None:
                    crt = crt.parent
                    direction = 'u'
                else:
                    crt = crt.parent.next
                    crtcopy, direction = self.__pre_link_node(
                        crt, crtcopy
                    )

    def update_log(self, log, after=True):
        """Append the messages from a `log` document to the
        converters log. This removes the children from `log`. """
        modules = log.modules
        explanation = log.explanation
        for mname in modules:
            if mname not in self.log[-1].modules:
                self.log[-1].modules[mname] = modules[mname]
            if mname not in self.log[-1].explanation:
                self.log[-1].explanation[mname] = explanation[mname]
        if after:
            self.log[-1].extend_children(log)
        else:
            self.log[-1].extend_before(0, log)

    # pylint: disable=W0122,E1103
    def exec_python(self, node, id_num, parser, error=True):
        """Executes the contents of the |PI| node. You must provide
        an id number identifying the processing instruction and a
        |Parser| that will parse the output provided by the
        execution. If `error` is True then any errors generated
        during the execution will be appended to the output of the
        document."""
        get_current_node.current.append(node)
        include.converter.append(self)
        namespace = get_lexor_namespace()
        if '__NAMESPACE__' not in namespace:
            namespace['__NAMESPACE__'] = namespace
            namespace['import_module'] = import_module
            namespace['include'] = include
            namespace['echo'] = echo
        namespace['__FILE__'] = pth.realpath(include.converter[-1].doc[-1].uri)
        namespace['__DIR__'] = pth.dirname(namespace['__FILE__'])
        namespace['__NODE__'] = get_current_node()
        original_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            exec(node.data, namespace)
        except BaseException:
            self.msg(self.__module__, 'E100', node, [id_num])
            if error:
                err_node = LC.Element('python_pi_error')
                err_node['section'] = str(id_num)
                err_node.append_child(
                    LC.CData(traceback.format_exc())
                )
                node.parent.insert_before(node.index, err_node)
        text = sys.stdout.getvalue()
        sys.stdout.close()
        sys.stdout = original_stdout
        parser.parse(text)
        node.parent.extend_before(node.index, parser.doc)
        newnode = Converter.remove_node(node)
        if parser.log:
            self.msg(self.__module__, 'W101', node, [id_num])
            self.update_log(parser.log)
            self.msg(self.__module__, 'W102', node, [id_num])
        get_current_node.current.pop()
        include.converter.pop()
        if include.converter:
            doc = include.converter[-1].doc[-1]
            namespace['__FILE__'] = pth.realpath(doc.uri)
            namespace['__DIR__'] = pth.dirname(namespace['__FILE__'])
            namespace['__NODE__'] = get_current_node()
        else:
            namespace['__FILE__'] = None
            namespace['__DIR__'] = None
            namespace['__NODE__'] = None
        return newnode


def get_lexor_namespace():
    """The execution of python instructions take place in the
    namespace provided by this function."""
    return get_lexor_namespace.namespace
if not hasattr(get_lexor_namespace, 'namespace'):
    get_lexor_namespace.namespace = dict()


def get_current_node():
    """Return the document node containing the python embeddings
    currently being executed. """
    return get_current_node.current[-1]
if not hasattr(get_current_node, 'current'):
    get_current_node.current = list()


def echo(node):
    """Allows the insertion of Nodes generated within python
    embeddings::

        <?python
        comment = PI('!--', 'This is a comment')
        echo(comment)
        ?>

    """
    crt = get_current_node()
    if isinstance(node, str):
        crt.parent.insert_before(crt.index, LC.Text(node))
    elif isinstance(node, LC.Node):
        if node.name == '#document':
            crt.parent.extend_before(crt.index, node)
            return
        crt.parent.insert_before(crt.index, node)
    elif isinstance(node, list):
        for item in node:
            echo(item)
    else:
        while node:
            echo(node[0])


def include(input_file, **keywords):
    """Inserts a file into the current node. Absolute paths may be
    provided as well as relative. When using relative paths the files
    are found relative to the path of the calling document. You may
    use the following keywords:
    
    - parser_style: ``'default'``
    - parser_lang: ``None``
    - parser_defaults: ``None``,
    - convert_style: ``'default'``,
    - convert_from: ``None``,
    - convert_to: ``None``,
    - convert_defaults: ``None``,
    - adopt: ``'true'``
    
    If the keyword ``adopt`` is set to false then a |Document| node
    will be inserted."""
    parent_converter = include.converter[-1]
    if input_file[0] != '/':
        input_file = pth.join(pth.dirname(parent_converter.doc.uri),
                              input_file)
    info = {
        'parser_style': 'default',
        'parser_lang': None,
        'parser_defaults': None,
        'convert_style': 'default',
        'convert_from': None,
        'convert_to': None,
        'convert_defaults': None,
        'adopt': True,
    }
    for key in keywords:
        info[key] = keywords[key]
    if info['parser_lang'] is None:
        path = pth.realpath(input_file)
        name = pth.basename(path)
        name = pth.splitext(name)
        info['parser_lang'] = name[1][1:]
    with open(input_file, 'r') as tmpf:
        text = tmpf.read()
    parser = LC.Parser(info['parser_lang'],
                       info['parser_style'],
                       info['parser_defaults'])
    parser.parse(text, input_file)
    if parser.log:
        parent_converter.update_log(parser.log)
    crt = get_current_node()
    if info['convert_to'] is not None:
        if info['convert_from'] is None:
            info['convert_from'] = info['parser_lang']
        converter = Converter(info['convert_from'],
                              info['convert_to'],
                              info['convert_style'],
                              info['convert_defaults'])
        converter.convert(parser.doc)
        if converter.log:
            parent_converter.update_log(converter.log)
        doc = converter.document
    else:
        doc = parser.doc
    if info['adopt']:
        crt.parent.extend_before(crt.index, doc)
    else:
        crt.parent.insert_before(crt.index, doc)
if not hasattr(include, 'converter'):
    include.converter = list()


def import_module(mod_path, mod_name=None):
    """Return a module from a path. If no name is provided then the
    name of the file loaded will be assigned to the name. When using
    relative paths, it will find the module relative to the file
    executing the python embedding. """
    doc = include.converter[-1].doc[-1]
    if not mod_path.endswith('.py'):
        mod_path += '.py'
    if mod_path[0] != '/':
        mod_path = pth.join(pth.dirname(doc.uri), mod_path)
    if mod_name is None:
        mod_name = pth.basename(mod_path)
    if mod_name.endswith('.py'):
        mod_name = mod_name[:-3]
    return load_source(mod_name, mod_path)


MSG = {
    'E100': 'errors in python processing instruction section `{0}`',
    'W101': '--> begin ?python section `{0}` messages',
    'W102': '--> end ?python section `{0}` messages',
}
MSG_EXPLANATION = [
    """
    - This message is being shown because of E100.

    - The python processing instructions has mistakes. See the
      traceback generated to fix the errors.

    - If the traceback is not shown in the document it may be
      due to the option `error` being off.

""",
    """
    - Python embeddings may generate output to be adapted to the
      document. Such output also needs to be processed. When the
      output generates errors these errors get appended to the
      converter log document.

    - All messages between W101 and W102 are are simply errors of the
      parsed output.

""",
]
