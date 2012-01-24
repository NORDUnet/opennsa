"""
Decoding and encoding of SOAP request via WSDL description.

Original version by Dieter Maurer (dm.zope.rpc.wsdl_suds package).

Modified by Henrik Thostrup Jensen to not be tied into Zope and be a bit more
generic and support for soap action and custom types.

Copyright (C) 2010 by Dr. Dieter Maurer <dieter@handshake.de>
Copyright (C) 2011-2012 by Henrik Thostrup Jensen <htj@nordu.net>

License: BSD
"""

from suds.client import Client
from suds.sax.parser import Parser



class WSDLMarshaller:
    """
    Generic marshaller for SOAP described by WSDL.
    """
    def __init__(self, wsdl_url):
        self.client = Client(wsdl_url)

        self.soap_actions = self.soapActions()
        self.method_map = {}


    def recognizedSOAPAction(self, soap_action):
        """
        Returns true if soap_action is recognized by the WSDL.

        @args: soap_action The SOAP action.
        """

        return soap_action in self.soap_actions


    def createType(self, type_name):
        """
        @args typename: type to create. QNames are specified with {namespace}element syntax.
        """
        return self.client.factory.create(type_name)


    def parse_request(self, method_name, data):
        """"
        @args: method_name Short version of soap_action.
        @args: raw soap data (string)
        """
        root = Parser().parse(string=data)
        env = root.getChild('Envelope')
        env.promotePrefixes()
        body = env.getChild('Body')

        method = self.method = self._lookup(method_name)

        binding = method.binding.input
        # code extracted from "suds.bindings.binding.Binding.get_reply"
        body = binding.multiref.process(body)
        nodes = binding.replycontent(method, body)
        # Note: "method" has its input and output exchanged.
        # Therefore, "returned_types" in fact means "parameter_types".
        rtypes = binding.returned_types(method)
        params = binding.replycomposite(rtypes, nodes)
        # the normalization part does not seem to do anything usefull
        return method, params


    def marshal_result(self, value, method):
        # the interpretation of "value" is a bit ambiguous: Unlike SOAP, Python
        # does not support named output parameters nor multiple return values
        # (not suggested by SOAP but easily modellable). Python only supports a
        # single return value; everything else needs emulation.

        #  Following the example of ``suds.bindings.binding.Bindingget_reply``,
        #  we use WSDL inspection to get hints how to map *value* to the
        #  result.

        # Note: ``method.unwrapped`` gives the original method (input and output
        #  not exchanged)
        rtypes = method.binding.output.returned_types(method.unwrapped_)
        # determine *args* and *kw* from *value* depending on how
        #  the WSDL wants the result
        if len(rtypes) == 0:
            # the WSDL does not want a return value
            args, kw = (), {}
        elif len(rtypes) == 1:
            # the WSDL wants a single return value -- use *value*
            args, kw = (value,), {}
        else:
            # the WSDL wants a sequence of values
            #  we pass *value" as *kw*, if it is a dict; otherwise as *args*.
            #  In the latter case, *value* must be a sequence and
            #  we strip away excess values (and hope
            #  this happens automatically in the former case)
            if isinstance(value, dict): args, kw = (), value
            else: args, kw = value[:len(rtypes)], {}

        reply = method.binding.output.get_message(method, args, kw)
        return str(reply.str())


    def marshal_exception(self, exc, method):

        raise NotImplementedError("cannot yet handle exceptions")

        # The following code is very much unfinished and there is no
        # guaranty that it is correct or even makes sense
        # Currently it finds the fault return types (there should only
        # be one AFAICT). How to get from there and to to a fault body
        # is still open.

        from suds.xsd.query import TypeQuery, ElementQuery

        rtypes = []

        for f in method.unwrapped_.soap.faults:
            for p in f.parts:
                if p.element is not None:
                    query = ElementQuery(p.element)
                else:
                    query = TypeQuery(p.type)
                pt = query.execute(method.binding.output.schema())
                if pt is None:
                    raise TypeNotFound(query.ref)
                if p.type is not None:
                    pt = PartElement(p.name, pt)
                rtypes.append(pt)

        return rtypes


    def soapActions(self):

        soap_actions = []

        # Should really iterate over all services/ports here
        for (name, element) in self.client.wsdl.bindings.values()[0]:
            if name == 'operations':
                for method_name, method in element.items():
                    soap_actions.append(method.soap.action)

        return soap_actions


    def _lookup(self, method_name):
        """
        look up a method in the WSDL.

        As we are using ``suds`` on the server (rather than client) side, we
        must exchange its ``input`` and ``output`` in order not to invalidate
        internally expected invariants (to be specific: ``get_reply`` always
        uses ``sopa.output`` and ``get_messages`` ``soap.input`` of a method).
        We use access transformers to achieve this.
        """

        method = getattr(self.client.service, method_name).method
        return _InputOutputExchanger(method)



class _InputOutputExchanger(object):
    """
    Exchange method's ``input`` and ``output`` binding.
    """
    unwrapped_ = None

    def __init__(self, method): self.unwrapped_ = method

    def __getattr__(self, attr):
        if attr == 'soap':
            return _InputOutputExchanger2(self.unwrapped_.soap)
        return getattr(self.unwrapped_, attr)



class _InputOutputExchanger2(object):
    """
    Exchange binding's ``input`` and ``output`` attributes.
    """

    __soap = None

    def __init__(self, soap):
        self.__soap = soap

    def __getattr__(self, attr):
        if attr == 'input': attr = 'output'
        elif attr == 'output': attr = 'input'
        return getattr(self.__soap, attr)

