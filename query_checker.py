from arpeggio import PTNodeVisitor, visit_parse_tree, NoMatch, SemanticError, \
    ParserPython, RegExMatch as _r, Optional, ZeroOrMore, Sequence, EOF, OneOrMore, Not, And


class MongoRestoreQueryChecker:
    '''
    A restore query should look like
    /*
     * WHERE
     *     DATA_TYPE FIELD1 = TERM1 AND DATA_TYPE FIELD2 > TERM2 OR DATA_TYPE FIELD3 != TERM3
     */
    This class will only check input query and return true or false.
    GRAMMAR is the PEG syntax for defining the syntax
    '''

    class QueryVisitor(PTNodeVisitor):
        '''
        Class to parse the parse tree generated.
        Based on the definition of the grammar, every rule can have a visit_xxx call. The return value is what is seen
        as children to the parent rule. For a rule only the variables would be seen as children, string literals
        are never visited or never returned. E.g. the rule for ttloperation = "TTL = <variable>", "TTL" and "=" being
        literals, children[0] will have the value of the <variable>, the literals are never matched in children.
        '''
        def __init__(self):
            super(MongoRestoreQueryChecker.QueryVisitor, self).__init__()
            # This dictionary will keep records of all elements that were traverse
            self.bracket_list = []

        def visit_left_brace(self, node, children):
            self.bracket_list.append(node.value)
            print node.value
            print(self.bracket_list)

        def visit_right_brace(self, node, children):
            print node.value
            if len(self.bracket_list) > 0:
                self.bracket_list.pop()
                print(self.bracket_list)
            else:
                return "Error"

        def visit_term_raw(self, node, children):
            print node.value

    def __init__(self, restore_query):

        '''
        @type restore_query: str
        @param restore_query: Mongo restore query
        For general instructions on how we came up to this grammar read
        http://www.igordejanovic.net/Arpeggio/grammars/#grammars-written-in-python
        General Rule:
            Sequence is represented as Python tuple.
            Ordered choice is represented as Python list where each element is one alternative.
            One or more is represented as an instance of OneOrMore class. The parameters are treated as a containing
                sequence.
            Zero or more is represented as an instance of ZeroOrMore class. The parameters are treated as a containing
                sequence.
            Optional is represented as an instance of Optional class.
            Unordered group is represented as an instance of UnorderedGroup class. (not used)
            And predicate is represented as an instance of And class. (not used)
            Not predicate is represented as an instance of Not class. (not used)
            Literal string match is represented as string or regular expression given as an instance of RegExMatch
                class. (used as _r)
            End of string/file is recognized by the EOF special rule.
        '''

        def start():
            return restore_stmt, EOF

        def restore_stmt():
            return [u"SELECT", u"select"], sclause, Optional([u"WHERE", u"where"], wclause)

        def wclause():
            return [_all, (braced_restriction, ZeroOrMore(_bool_type, braced_restriction))]

        def sclause():
            return [u"*", (select_field, ZeroOrMore(([u",", u"."], select_field)))]

        def select_field():
            return _r(r'\w+')

        def _all():
            return u"*"

        def _bool_type():
            return [_and, _or]

        def _and():
            return [u"and", u"AND"]

        def _or():
            return [u"or", u"OR"]

        def left_brace():
            return u"("

        def right_brace():
            return u")"

        def _restriction():
            return _data_type, _field, [(_relation_type, _term), exist_or_not]

        def braced_restriction():
            return ZeroOrMore(left_brace), _restriction, ZeroOrMore(right_brace)

        def _field():
            return [single_quoted_field, field_raw]

        def single_quoted_field():
            # Match everything that falls under a '' and also match escaped ' (\')
            return u"'", Sequence(OneOrMore([_r(r'[^\x27\\]'), (u"\\", _r(r'.'))]), skipws=False), u"'"

        def field_raw():
            return _r(r'[^,\s]+')

        def _relation_type():
            return [u"<=", u"!=", u">=", u"=", u"<", u">"]

        def _term():
            return [single_quoted_term, term_raw]

        def single_quoted_term():
            # Match everything that falls under a '' and also match escaped ' (\')
            return u"'", Sequence(OneOrMore([_r(r'[^\x27\\]'), (u"\\", _r(r'.'))]), skipws=False), u"'"

        def term_raw():
            return _r(r'[^\)]+')

        def not_exist():
            return u'!'

        def _exist():
            return u'*'

        def exist_or_not():
            return [not_exist, _exist]

        def _data_type():
            return [u'eod', u'double', u'utf8', u'document', u'array', u'binary', u'undefined', u'oid',
                    u'bool', u'date_time', u'null', u'regex', u'dbpointer', u'code', u'symbol', u'codewscope',
                    u'int32', u'timestamp', u'int64', u'decimal128', u'maxkey', u'minkey']

        self.restore_query = restore_query
        self.parser = ParserPython(start, debug=False)
        self.parse_tree = None
        self.tree_visitor = None

    def parse_query(self):
        try:
            self.parse_tree = self.parser.parse(self.restore_query)
        except NoMatch as err:
            return "Error"
        self.tree_visitor = self.QueryVisitor()

        # visit_parse_tree is an arpeggio method to parse the parse_tree created from the query
        try:
            visit_parse_tree(self.parse_tree, self.tree_visitor)
        except SemanticError as err:
            return str(err)
        if len(self.tree_visitor.bracket_list) != 0:
            return "Error: brackets not valid"

        return "Success"


target_query = "SELECT * WHERE (int32 a > 54) AND ((int32 b <  10))"

query_parser = MongoRestoreQueryChecker(target_query)
print query_parser.parse_query()
