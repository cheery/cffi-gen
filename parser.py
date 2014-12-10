from subprocess import check_output
from tokenizer import tokenize
import lrkit
from lrkit import canonical, Rule, Accept
import operator
import re

class Environment(object):
    def __init__(self):
        self.enums = {}
        self.unions = {}
        self.structs = {'__locale_data': Structure(None)}
        self.types = {}
        self.constants = {}
        self.names = {}
        self.hard_to_parse_macros = {}
        self.unparsed_parametric_macros = {}

class Specifier(object):
    def __init__(self):
        self.qualifiers = set()
        self.specifiers = []

    def __repr__(self):
        return ' '.join(list(self.qualifiers) + map(str, self.specifiers))

class Declarator(object):
    def __init__(self, name):
        self.name = name
        self.initializer = None
        self.attributes = ()
        self.specifiers = []
        self.qualifiers = set()
        self.stack = []

    def __getitem__(self, index):
        return self.stack[index]

    def __len__(self):
        return len(self.stack)

    def __repr__(self):
        return "%s %s %r" % (self.name, ' '.join(map(repr, self.stack)), ' '.join(list(self.qualifiers) + map(str, self.specifiers)))

class Enum(object):
    def __init__(self, constants):
        self.constants = constants

class Structure(object):
    def __init__(self, fields):
        self.fields = fields

class Union(object):
    def __init__(self, fields):
        self.fields = fields


rules = []
labelled_rules = {}

def rule(string, label=None):
    lhs, rhs = string.split(' = ')
    rule = Rule(lhs.strip(), [a for a in rhs.strip().split(' ') if len(a) > 0])
    if label is not None:
        labelled_rules[label] = rule
    def _impl_(func):
        rule.func = func
        return func
    rules.append(rule)
    return _impl_

@rule('translation_unit = ')
@rule('blank_list = ')
def on_blank_list(lineno, env):
    return []

@rule('blank = ')
def on_blank(lineno, env):
    return None

@rule('declaration_list = declaration')
@rule('init_declarator_list = init_declarator')
@rule('initializer_list = initializer')
@rule('identifier_list = IDENTIFIER')
@rule('parameter_list = parameter_declaration')
@rule('struct_declarator_list = struct_declarator')
@rule('enumerator_list = enumerator')
@rule('type_qualifier_list = type_qualifier')
@rule('attribute_specifier_list = attribute_specifier', label="declarator_attribute")
@rule('attribute_list = attribute')
def on_list(lineno, env, obj):
    return [obj]

@rule('translation_unit = translation_unit external_declaration')
@rule('declaration_list = declaration_list declaration')
@rule('type_qualifier_list = type_qualifier_list type_qualifier')
@rule('attribute_specifier_list = attribute_specifier_list attribute_specifier')
def on_append(lineno, env, seq, obj):
    seq.append(obj)
    return seq

@rule('struct_declaration_list = struct_declaration')
def on_flat_list(lineno, env, obj):
    return obj

@rule('struct_declaration_list = struct_declaration_list struct_declaration')
def on_flat_extend(lineno, env, obj, more):
    obj.extend(more)
    return obj

@rule('init_declarator_list = init_declarator_list COMMA init_declarator')
@rule('initializer_list = initializer_list COMMA initializer')
@rule('identifier_list = identifier_list COMMA IDENTIFIER')
@rule('parameter_list = parameter_list COMMA parameter_declaration')
@rule('struct_declarator_list = struct_declarator_list COMMA struct_declarator')
@rule('enumerator_list = enumerator_list COMMA enumerator')
@rule('attribute_list = attribute_list COMMA attribute')
def on_separator_append(lineno, env, seq, sep, obj):
    seq.append(obj)
    return seq

@rule('external_declaration = function_definition')
@rule('external_declaration = declaration')
def on_passthrough(lineno, env, obj):
    return obj

@rule('declaration = declaration_specifiers blank_list SEMICOLON')
@rule('declaration = declaration_specifiers init_declarator_list SEMICOLON')
def on_declaration(lineno, env, specifier, declarators, *sm):
    typedef = 'typedef' in specifier.qualifiers
    for declarator in declarators:
        assert isinstance(declarator, Declarator)
        declarator.specifiers = specifier.specifiers
        declarator.qualifiers = specifier.qualifiers
        if typedef:
            env.types[declarator.name] = declarator
        else:
            env.names[declarator.name] = declarator
    return declarators

# commented out, because they unlikely appear in a header file,
# and they would interfere with the simple interpretation of declaration above.
#@rule('function_definition = declaration_specifiers declarator declaration_list compound_statement')
@rule('function_definition = declaration_specifiers declarator attribute_specifier_list compound_statement')
@rule('function_definition = declaration_specifiers declarator compound_statement')
#@rule('function_definition = declarator declaration_list compound_statement')
@rule('function_definition = declarator attribute_specifier_list compound_statement')
@rule('function_definition = declarator compound_statement')
def on_function_definition(lineno, env, *stuff):
    return stuff

@rule('declarator = pointer direct_declarator')
def on_declarator_pointer(lineno, env, pointers, declarator):
    declarator.stack.extend(pointers)
    return declarator

@rule('pointer = STAR blank_list')
@rule('pointer = STAR type_qualifier_list')
def on_one_pointer(lineno, env, star, qualifier_list):
    return [('pointer', set(qualifier_list))]

@rule('pointer = STAR blank_list pointer')
@rule('pointer = STAR type_qualifier_list pointer')
def on_many_pointers(lineno, env, star, qualifier_list, pointer):
    return [('pointer', set(qualifier_list))] + pointer

@rule('declarator = direct_declarator')
def on_declarator(lineno, env, declarator):
    return declarator

@rule('direct_declarator = IDENTIFIER')
def on_direct_declarator_simple(lineno, env, declarator):
    return Declarator(declarator)

@rule('direct_declarator = LEFT_PAREN declarator RIGHT_PAREN')
def on_pointer_declarator_simple(lineno, env, lp, declarator, rp):
    return declarator

@rule('direct_declarator = direct_declarator LEFT_BRACKET blank RIGHT_BRACKET')
@rule('direct_declarator = direct_declarator LEFT_BRACKET constant_expression RIGHT_BRACKET')
def on_direct_declarator_bracket(lineno, env, declarator, lp, index, rp):
    declarator.stack.append(('array', index))
    return declarator

@rule('direct_declarator = direct_declarator LEFT_PAREN blank RIGHT_PAREN')
@rule('direct_declarator = direct_declarator LEFT_PAREN parameter_type_list RIGHT_PAREN')
#@rule('direct_declarator = direct_declarator LEFT_PAREN identifier_list RIGHT_PAREN')
def on_direct_declarator(lineno, env, declarator, lp, arguments, rp):
    declarator.stack.append(('function', arguments))
    return declarator

@rule('parameter_type_list = parameter_list')
@rule('parameter_type_list = parameter_list COMMA DOT DOT DOT')
def on_parameter_type_list(lineno, env, parameters, *ellipsis):
    if len(ellipsis) > 0:
        parameters.append(Ellipsis)
    return parameters

@rule('parameter_declaration = declaration_specifiers declarator')
@rule('parameter_declaration = declaration_specifiers abstract_declarator')
@rule('parameter_declaration = declaration_specifiers blank_abstract_declarator')
def on_parameter_declaration(lineno, env, specifier, declarator):
    declarator.specifiers = specifier.specifiers
    declarator.qualifiers = specifier.qualifiers
    return declarator

@rule('abstract_declarator = pointer')
def on_blank_abstract_declarator(lineno, env, pointers=()):
    declarator = Declarator(None)
    declarator.stack.extend(pointers)
    return declarator

@rule('abstract_declarator = direct_abstract_declarator')
def on_direct_abstract_declarator(lineno, env, declarator):
    return declarator

@rule('abstract_declarator = pointer direct_abstract_declarator')
def on_pointer_abstract_declarator(lineno, env, pointers, declarator):
    declarator.stack.extend(pointers)
    return declarator

@rule('direct_abstract_declarator = LEFT_PAREN abstract_declarator RIGHT_PAREN')
def on_abstract_declarator_parens(lineno, env, lp, declarator, rp):
    return declarator

@rule('direct_abstract_declarator = LEFT_BRACKET blank RIGHT_BRACKET')
@rule('direct_abstract_declarator = LEFT_BRACKET constant_expression RIGHT_BRACKET')
def on_abstract_declarator_brackets(lineno, env, lp, index, rp):
    declarator = Declarator(None)
    declarator.stack.append(('array', index))
    return declarator

@rule('direct_abstract_declarator = direct_abstract_declarator LEFT_BRACKET blank  i            RIGHT_BRACKET')
@rule('direct_abstract_declarator = direct_abstract_declarator LEFT_BRACKET constant_expression RIGHT_BRACKET')
def on_abstract_declarator_along_brackets(lineno, env, declarator, lp, index, rp):
    declarator.stack.append(('array', index))
    return declarator

@rule('direct_abstract_declarator = direct_abstract_declarator LEFT_PAREN blank_list          RIGHT_PAREN')
@rule('direct_abstract_declarator = direct_abstract_declarator LEFT_PAREN parameter_type_list RIGHT_PAREN')
def on_abstract_declarator_function(lineno, env, declarator, lp, arguments, rp):
    declarator.stack.append(('function', arguments))
    return declarator

@rule('blank_abstract_declarator = ')
def on_blank_abstract_declarator(lineno, env):
    return Declarator(None)

@rule('blank_declaration_specifier = ')
def on_blank_declaration_specifier(lineno, env):
    return Specifier()

@rule('declaration_specifiers = blank_declaration_specifier storage_class_specifier')
@rule('declaration_specifiers = declaration_specifiers      storage_class_specifier')
@rule('declaration_specifiers = blank_declaration_specifier type_qualifier')
@rule('declaration_specifiers = declaration_specifiers      type_qualifier')
@rule('specifier_qualifier_list = blank_declaration_specifier type_qualifier')
@rule('specifier_qualifier_list = specifier_qualifier_list type_qualifier')
def on_qualifier(lineno, env, block, qualifier):
    if isinstance(qualifier, str):
        block.qualifiers.add(qualifier)
    else:
        which, info = qualifier
    return block

@rule('declaration_specifiers = blank_declaration_specifier type_specifier')
@rule('declaration_specifiers = declaration_specifiers      type_specifier')
@rule('specifier_qualifier_list = blank_declaration_specifier type_specifier')
@rule('specifier_qualifier_list = specifier_qualifier_list type_specifier')
def on_specifier(lineno, env, block, specifier):
    block.specifiers.append(specifier)
    return block


#@rule('specifier_qualifier_list = specifier_qualifier')
#@rule('specifier_qualifier_list = specifier_qualifier_list specifier_qualifier')

#@rule('specifier_qualifier = type_specifier')
#@rule('specifier_qualifier = type_qualifier')
#def on_specifier_qualifier(lineno, env, specifier):
#    return specifier

@rule('storage_class_specifier = attribute_specifier', label="storage_attribute")
@rule('storage_class_specifier = TYPEDEF')
@rule('storage_class_specifier = EXTERN')
@rule('storage_class_specifier = STATIC')
@rule('storage_class_specifier = AUTO')
@rule('storage_class_specifier = REGISTER')
@rule('storage_class_specifier = INLINE')
@rule('storage_class_specifier = __INLINE')
@rule('storage_class_specifier = __INLINE__')
@rule('storage_class_specifier = __THREAD')
def on_storage_class_specifier(lineno, env, specifier):
    return specifier

@rule('type_specifier = VOID')
@rule('type_specifier = CHAR')
@rule('type_specifier = SHORT')
@rule('type_specifier = INT')
@rule('type_specifier = LONG')
@rule('type_specifier = FLOAT')
@rule('type_specifier = DOUBLE')
@rule('type_specifier = SIGNED')
@rule('type_specifier = __SIGNED__')
@rule('type_specifier = UNSIGNED')
@rule('type_specifier = struct_or_union_specifier')
@rule('type_specifier = enum_specifier')
@rule('type_specifier = TYPE_NAME')
def on_type_specifier(lineno, env, specifier):
    return specifier

@rule('type_qualifier = CONST')
@rule('type_qualifier = VOLATILE')
@rule('type_qualifier = __RESTRICT')
@rule('type_qualifier = __RESTRICT__')
@rule('type_qualifier = __EXTENSION__')
def on_type_qualifier(lineno, env, qualifier):
    return qualifier


@rule('init_declarator = declarator attribute_specifier_list')
@rule('init_declarator = declarator')
def on_init_declarator(lineno, env, declarator, attributes=()):
    declarator.attributes = attributes
    return declarator

@rule('init_declarator = declarator EQUAL initializer')
def on_init_declarator_init(lineno, env, declarator, eq, initializer):
    declarator.initializer = initializer
    return declarator

@rule('attribute_specifier = __ASM__ LEFT_PAREN attribute_list RIGHT_PAREN')
def on_attribute_specifier(lineno, env, at, lp1, attributes, rp2):
    return ('asm', attributes)

@rule('attribute_specifier = __ATTRIBUTE__ LEFT_PAREN LEFT_PAREN attribute_list RIGHT_PAREN RIGHT_PAREN')
def on_attribute_specifier(lineno, env, at, lp1, lp2, attributes, rp1, rp2):
    return ('attribute', attributes)

@rule('attribute = STRING')
@rule('attribute = IDENTIFIER')
@rule('attribute = INTCONSTANT')
def on_attribute_term(lineno, env, stuff):
    return stuff

@rule('attribute = STRING STRING')
def on_attribute_string_pair(lineno, env, lhs, rhs):
    return ['pair', lhs, rhs]

@rule('attribute = IDENTIFIER LEFT_PAREN attribute_list RIGHT_PAREN')
def on_attribute(lineno, env, label, lp, sequence, rp):
    return [label] + sequence

@rule('initializer = assignment_expression')
def on_initializer_assignment_expression(lineno, env, expr):
    return expr

@rule('initializer = LEFT_BRACE initializer_list RIGHT_BRACE')
@rule('initializer = LEFT_BRACE initializer_list COMMA RIGHT_BRACE')
def on_initializer_list(lineno, env, lb, initlist, *rest):
    return initlist

@rule('struct_or_union_specifier = struct_or_union struct_identifier LEFT_BRACE struct_declaration_list RIGHT_BRACE')
@rule('struct_or_union_specifier = struct_or_union blank             LEFT_BRACE struct_declaration_list RIGHT_BRACE')
@rule('struct_or_union_specifier = struct_or_union struct_identifier')
def on_struct_or_union_specifier(lineno, env, which, name, lb=None, block=None, rb=None):
    cls, space = which
    obj = space[name] if name in space else cls(None)
    if block is not None:
        obj.fields = block
    if name is not None:
        space[name] = obj
    return obj

@rule('struct_identifier = IDENTIFIER')
@rule('struct_identifier = TYPE_NAME')
def on_struct_identifier(lineno, env, name):
    return name

@rule('struct_or_union = STRUCT')
@rule('struct_or_union = UNION')
def on_struct_or_union(lineno, env, which):
    return {'struct':(Structure, env.structs), 'union':(Union, env.unions)}[which]

@rule('struct_declaration = specifier_qualifier_list struct_declarator_list SEMICOLON')
def on_struct_declaration(lineno, env, specifier, declarators, sm):
    for declarator in declarators:
        declarator.specifiers = specifier.specifiers
        declarator.qualifiers = specifier.qualifiers
    return declarators

@rule('struct_declarator = declarator')
def on_blank_struct_declarator(lineno, env, declarator):
    return declarator

@rule('struct_declarator = COLON constant_expression')
def on_bitfield_declarator(lineno, env, colon, expr):
    declarator = Declarator(None)
    declarator.stack.append(('bitfield', expr))
    return declarator

@rule('struct_declarator = declarator COLON constant_expression')
def on_bitfield_struct_declarator(lineno, env, declarator, colon, expr):
    declarator.stack.append(('bitfield', expr))
    return declarator

@rule('enum_specifier = ENUM LEFT_BRACE enumerator_list RIGHT_BRACE')
def on_plain_enum_specifier(lineno, env, enum, lb, constants, rb):
    return Enum(constants)

@rule('enum_specifier = ENUM IDENTIFIER LEFT_BRACE enumerator_list RIGHT_BRACE')
def on_named_enum_specifier(lineno, env, enum, name, lb, constants, rb):
    enum = env.enums[name] if name in env.enums else Enum(None)
    enum.constants = constants
    if name in env.enums:
        env.enums[name] = enum
    return enum

@rule('enum_specifier = ENUM IDENTIFIER')
def on_enum_specifier(lineno, env, enum, name):
    enum = env.enums[name] if name in env.enums else Enum(None)
    if name in env.enums:
        env.enums[name] = enum
    return enum

@rule('enumerator = IDENTIFIER')
def on_implicit_enumerator(lineno, env, ident):
    return (ident, None)

@rule('enumerator = IDENTIFIER EQUAL constant_expression')
def on_enumerator(lineno, env, ident, eq, const):
    return (ident, const)

@rule('compound_statement = LEFT_BRACE RIGHT_BRACE')
@rule('compound_statement = LEFT_BRACE statement_list RIGHT_BRACE')
#@rule('compound_statement = LEFT_BRACE declaration_list RIGHT_BRACE')
@rule('statement_list = statement')
@rule('statement_list = statement_list statement')
@rule('statement = compound_statement')
@rule('statement = *')
def on_ignore_it_all(lineno, env, *ignore):
    return None

@rule('constant_expression = constant_comparison QUESTION constant_comparison COLON constant_comparison')
def on_const_comparison(lineno, env, cond, q, tru, c, fal):
    return [tru, fal][cond]

@rule('constant_expression = constant_bitor')
@rule('constant_bitor = constant_comparison')
@rule('constant_comparison = constant_shift')
@rule('constant_shift = constant_plusminus')
@rule('constant_plusminus = constant_divmul')
@rule('constant_divmul = constant_term')
def on_const_expression(lineno, env, value):
    return value

@rule('constant_bitor = constant_bitor VERTICAL_BAR constant_comparison')
@rule('constant_comparison = constant_comparison LEFT_ANGLE constant_shift')
@rule('constant_comparison = constant_comparison RIGHT_ANGLE constant_shift')
@rule('constant_comparison = constant_comparison EQ_OP constant_shift')
@rule('constant_shift = constant_shift LEFT_OP constant_plusminus')
@rule('constant_shift = constant_shift RIGHT_OP constant_plusminus')
@rule('constant_plusminus = constant_plusminus PLUS constant_divmul')
@rule('constant_plusminus = constant_plusminus DASH constant_divmul')
@rule('constant_divmul = constant_divmul SLASH constant_term')
@rule('constant_divmul = constant_divmul STAR constant_term')
def on_const_binop(lineno, env, lhs, op, rhs):
    value = operator_table[op](lhs, rhs)
    return value

operator_table = {
    '|':operator.or_,
    '==':operator.eq,
    '<<':operator.lshift,
    '>>':operator.rshift,
    '<':operator.lt,
    '>':operator.gt,
    '/':operator.div,
    '*':operator.mul,
    '-':operator.sub,
    '+':operator.add,
}

@rule('constant_term = IDENTIFIER')
def on_minus_prefix(lineno, env, value):
    # BAD: incorrect, fix
    return 0

@rule('constant_term = CHARACTER')
def on_minus_prefix(lineno, env, value):
    return ord(value)

@rule('constant_term = PLUS constant_term')
def on_plus_prefix(lineno, env, dash, value):
    return +value

@rule('constant_term = DASH constant_term')
def on_minus_prefix(lineno, env, dash, value):
    return -value

@rule('constant_term = LEFT_PAREN constant_expression RIGHT_PAREN')
def on_int_constant(lineno, env, lp, value, rp):
    return value

@rule('constant_term = SIZEOF LEFT_PAREN type_expression RIGHT_PAREN')
def on_sizeof_term(lineno, env, sz, lp, typesign, rp):
    # BAD: incorrect, fix.
    return 8

@rule('constant_term = LEFT_PAREN type_expression RIGHT_PAREN constant_term')
def on_sizeof_term(lineno, env, lp, typesign, rp, ct):
    return ct

@rule('constant_term = STRING')
@rule('constant_term = INTCONSTANT')
@rule('constant_term = FLOATCONSTANT')
def on_constant_expression_int(lineno, env, const):
    return const

@rule('type_expression = specifier_qualifier_list')
@rule('type_expression = specifier_qualifier_list pointer')
def on_type_expression(lineno, env, *rest):
    return rest

@rule('macro_expression = ')
def on_blank_macro_expression(lineno, env):
    return None

@rule('macro_expression = constant_expression')
def on_macro_expression(lineno, env, const):
    return const

## must still parse __mode__
##@rule('by-the-way = TYPEDEF type-prefixes type-sign IDENTIFIER __ATTRIBUTE__ LEFT_PAREN LEFT_PAREN __MODE__ LEFT_PAREN IDENTIFIER RIGHT_PAREN RIGHT_PAREN RIGHT_PAREN SEMICOLON')
##def on_typedef_structure(lineno, td, tp, i, name, at, lp1, lp2, md, lp3, ident, rp1, rp2, rp3, sm):
##    assert ident in mode_types, "%i: unknown mode(%s)" % (lineno, ident)
##    type_space[name] = mode_types[ident]
#
#@rule('by-the-way = TYPEDEF type-prefixes type-sign IDENTIFIER LEFT_BRACKET const-expression RIGHT_BRACKET SEMICOLON')
#def on_array_thingy(lineno, td, tp, typesign, name, lb, value, rb, sm):
#    type_space[name] = ('array', typesign, value)
#
#@rule('by-the-way = TYPEDEF type-prefixes type-sign IDENTIFIER LEFT_PAREN argument-list RIGHT_PAREN SEMICOLON')
#def on_function_pointer(lineno, td, tp, restype, name, lp, argtypes, rp, sm):
#    type_space[name] = ('functype', restype, argtypes)
#
#@rule('by-the-way = TYPEDEF type-prefixes type-sign LEFT_PAREN STAR IDENTIFIER RIGHT_PAREN LEFT_PAREN argument-list RIGHT_PAREN SEMICOLON')
#def on_function_pointer2(lineno, td, tp, restype, lp, st, name, rp, lp2, argtypes, rp2, sm):
#    type_space[name] = ('functype', restype, argtypes)
#
#@rule('by-the-way = STATIC inline-mark type-sign IDENTIFIER LEFT_PAREN argument-list RIGHT_PAREN LEFT_BRACE trash-brace-block RIGHT_BRACE')
#@rule('trash-brace-block = ')
#@rule('trash-brace-block = trash-brace-block *')
#@rule('trash-brace-block = trash-brace-block LEFT_BRACE trash-brace-block RIGHT_BRACE')
#@rule('inline-mark = __INLINE')
#@rule('inline-mark = INLINE')
#def on_inline_statement(lineno, *trash):
#    pass
#
#
##@rule('declaration = name-pair SEMICOLON')
##def on_global_value(lineno, pair, sm):
##    return ('GLOBAL', pair[0], pair[1])
#
##@rule('declaration = type-sign IDENTIFIER LEFT_PAREN argument-list RIGHT_PAREN attribute-clauses SEMICOLON')
##def on_function(lineno, restype, name, lp, argtypes, rp, blah, sm):
##    return ('FUNCTION', name, (restype, argtypes))
#
#@rule('record-field = name-pair SEMICOLON')
#def on_record_field(lineno, pair, sm):
#    return pair
#
#@rule('argument = type-sign')
#@rule('argument = type-sign IDENTIFIER')
#@rule('argument = type-sign __RESTRICT')
#@rule('argument = type-sign __RESTRICT IDENTIFIER')
#def on_function_argument(lineno, typesign, *blah):
#    return typesign
#
#@rule('argument = DOT DOT DOT')
#def on_function_dot_dot_dot(lineno, dot1, dot2, dot3):
#    return None
#
#@rule('argument = argument LEFT_BRACKET RIGHT_BRACKET')
#def on_arb_array_argument(lineno, argtype, lb, rb):
#    return ('array', argtype, None)
#
#@rule('argument = argument LEFT_BRACKET const-expression RIGHT_BRACKET')
#def on_array_argument(lineno, argtype, lb, count, rb):
#    assert isinstance(count, int)
#    return ('array', argtype, count)
#
#@rule('argument = type-sign LEFT_PAREN STAR IDENTIFIER RIGHT_PAREN LEFT_PAREN argument-list RIGHT_PAREN')
#def on_functype_argument(lineno, restype, lp, st, name, rp, lp2, argtypes, rp2):
#    return ('functypen', restype, argtypes)
#
##@rule('name-pair = type-sign __RESTRICT IDENTIFIER')
##def on_name_restrict_pair(lineno, typesign, rs, name):
##    return (name, typesign)
#
#@rule('name-pair = type-sign IDENTIFIER COLON INTCONSTANT')
#def on_bit_horror(lineno, typesign, name, c, bitc):
#    return (name, ('bits', typesign, int(bitc)))
#
#@rule('name-pair = type-sign COLON INTCONSTANT')
#def on_more_bit_horror(lineno, typesign, c, bitc):
#    return (None, ('bits', typesign, int(bitc)))
#
#@rule('name-pair = type-sign IDENTIFIER')
#def on_name_pair(lineno, typesign, name):
#    return (name, typesign)
##
##@rule('name-pair = type-sign CONST IDENTIFIER')
##def on_name_pair_const(lineno, typesign, const, name):
##    return (name, typesign)
#
#@rule('name-pair = name-pair LEFT_BRACKET RIGHT_BRACKET')
#def on_arb_array_field(lineno, pair, lb, rb):
#    name, typesign = pair
#    return (name, ('array', typesign, None))
#
#@rule('name-pair = name-pair LEFT_BRACKET const-expression RIGHT_BRACKET')
#def on_array_field(lineno, pair, lb, count, rb):
#    name, typesign = pair
#    assert isinstance(count, int)
#    return (name, ('array', typesign, count))
#
#@rule('struct-union-header = UNION')
#def on_unnamed_union_header(lineno, st):
#    return Union(None)
#
#@rule('struct-union-header = STRUCT')
#def on_unnamed_struct_header(lineno, st):
#    return Structure(None)
#
#@rule('struct-union-header = UNION IDENTIFIER')
#@rule('struct-union-header = UNION TYPE')
#def on_named_union_header(lineno, st, name):
#    union_space[name] = union = union_space.get(name, Union(None))
#    return union
#
#@rule('struct-union-header = STRUCT IDENTIFIER')
#@rule('struct-union-header = STRUCT TYPE')
#def on_named_struct_header(lineno, st, name):
#    struct_space[name] = struct = struct_space.get(name, Structure(None))
#    return struct
#
#@rule('type-sign = CONST type-sign')
#def on_const(lineno, con, typesign):
#    return ('CONST', typesign)
#
#@rule('type-pointer = type-pointer STAR')
#@rule('type-pointer = type-pointer STAR CONST')
#def on_pointer_type(lineno, typesign, st, *con):
#    return Pointer(typesign)
#
#@rule('type-sign = type-pointer')
#@rule('type-pointer = type-term')
#def on_passthrough(lineno, typesign):
#    return typesign
#
#@rule('enum-header = ENUM')
#@rule('enum-header = ENUM IDENTIFIER')
#def on_enum(lineno, enum, *idents):
#    for ident in idents:
#        enum_space[ident] = prim_space['enum']
#    return prim_space['enum']
#
#@rule('by-the-way = enum-header LEFT_BRACE enum-list RIGHT_BRACE SEMICOLON')
#@rule('type-term = enum-header LEFT_BRACE enum-list RIGHT_BRACE')
#def on_enum(lineno, enum, lb, lists, rb, *blah):
#    for name, value in lists:
#        pass
#    return enum
#
#@rule('enum-name = IDENTIFIER')
#def on_enum_name(lineno, name):
#    return (name, None)
#
#@rule('enum-name = IDENTIFIER EQUAL const-expression')
#def on_enum_name(lineno, name, eq, value):
#    return (name, value)
#
#@rule('by-the-way = struct-union-header LEFT_BRACE struct-list RIGHT_BRACE SEMICOLON')
#@rule('type-term = struct-union-header LEFT_BRACE struct-list RIGHT_BRACE')
#def on_structure(lineno, struct, lb, fields, rb, *blah):
#    struct.fields = fields
#    return struct
#
#@rule('type-term = STRUCT IDENTIFIER')
#@rule('type-term = STRUCT TYPE')
#def on_struct_identifier(lineno, st, name):
#    struct_space[name] = struct = struct_space.get(name, Structure(None))
#    return struct
#
#@rule('type-term = UNION IDENTIFIER')
#@rule('type-term = UNION TYPE')
#def on_struct_identifier(lineno, st, ident):
#    return union_space[ident]
#
#@rule('type-term = TYPE')
#@rule('type-term = VOID')
##@rule('type-term = CHAR')
#def on_type_primitive(lineno, typesign):
#    return type_space[typesign]
#
#@rule('type-term = FLOAT')
#@rule('type-term = DOUBLE')
#@rule('type-term = LONG DOUBLE')
#def on_type_flonum(lineno, *flonum):
#    return prim_space[' '.join(flonum)]
#
#@rule('type-term = type-integer')
#def on_type_integer(lineno, typesign):
#    return typesign
#
#@rule('type-integer = UNSIGNED type-combination')
#def on_unsigned(lineno, un, prim):
#    return Unsigned(prim_space[prim].size)
#
#@rule('type-integer = SIGNED type-combination')
#def on_signed(lineno, un, prim):
#    return Unsigned(prim_space[prim].size)
#
#@rule('type-integer = type-combination')
#def on_int_default(lineno, prim):
#    return prim_space[prim]

translation_unit = canonical.simulate(rules, 'translation_unit')

attribute_conflict = set([labelled_rules['storage_attribute'], labelled_rules['declarator_attribute']])

remaining_conflicts = []
for row, name, group in translation_unit.conflicts:
    if group == attribute_conflict:
        translation_unit.table[row][name] = labelled_rules['declarator_attribute']
        continue
    remaining_conflicts.append((row, name, group))
translation_unit.conflicts = remaining_conflicts
assert len(translation_unit.conflicts) == 0, lrkit.diagnose(translation_unit)

macro_expression = canonical.simulate(rules, 'macro_expression')
assert len(macro_expression.conflicts) == 0, lrkit.diagnose(translation_unit)
print 'parsing'

class SnError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class Parser(object):
    def __init__(self, table, env):
        self.table = table
        self.state = 0
        self.stack = []
        self.data  = []
        self.env = env

    def step(self, lineno, group, value):
        if group == 'IDENTIFIER' and value in self.env.types:
            group = 'TYPE_NAME'
        action = self.table[self.state].get(group, self.table[self.state].get('*'))
        while isinstance(action, Rule):
            values = []
            for i in range(len(action)):
                self.state = self.stack.pop(-1)
                values.append(self.data.pop(-1))
            values.reverse()
            self.stack.append(self.state)
            self.data.append(action.func(lineno, self.env, *values))
            self.state = self.table[self.state][action.lhs]

            if group == 'IDENTIFIER' and value in self.env.types:
                group = 'TYPE_NAME'
            action = self.table[self.state].get(group, self.table[self.state].get('*'))
        if action is None:
            error = "%i: got %s, but expected %s: %s" % (lineno, group, ', '.join(map(str, self.table[self.state])), value)
            #if headers.find('namespace') >= 0 or headers.find('class') >= 0:
            #    raise Exception(error)
            #logs.write("%s:%s\n" % (path, error))
            #lines = headers.splitlines()
            #logs.write("-"*30 + "\n")
            #logs.write('\n'.join(lines[lineno-1:lineno+2]) + '\n')
            #logs.write("-"*30 + "\n")
            raise SnError(error)
        if isinstance(action, Accept):
            self.state  = self.stack.pop(-1)
            result = self.data.pop(-1)
            return result
        else:
            self.stack.append(self.state)
            self.data.append(value)
            self.state = action

macroregex = re.compile(r"(\w+(\([^\)]*\))?)\s*(.*)")

def parse(env, includes):
    includes = list(includes)
    parser = Parser(translation_unit.table, env)

    headers = check_output(['gcc', '-E'] + includes)
    token_stream = tokenize(headers)
    for lineno, group, value in token_stream:
        if group == 'MACRO':
            continue
        parser.step(lineno, group, value)
    result = parser.step(lineno, None, None)

    macros = check_output(['gcc', '-dM', '-E'] + includes)
    for line in [macro.strip() for macro in macros.split('#define')]:
        if line == "":
            continue
        match = macroregex.match(line)
        name, arglist, macrostring = match.groups()
        if arglist is None:
            groups = []
            values = []
            try:
                parser = Parser(macro_expression.table, env)
                for lineno, group, value in tokenize(macrostring.strip()):
                    parser.step(lineno, group, value)
                result = parser.step(lineno, None, None)
                if result is not None:
                    env.constants[name] = result
            except SnError as e:
                env.hard_to_parse_macros[name] = (macrostring, e)
        else:
            env.unparsed_parametric_macros[name] = (name, arglist, macrostring)
    return result

#env = None
#attributes = []
##proc = Popen(['gcc', '-E', argv[1]], stdout=PIPE)
##print proc.stdout.read()
#
#logs = open('logfile', 'a')
#for path in argv[1:]:
#    try:
#        reset_env()
#        state = 0
#        stack = []
#        data  = []
#        headers = check_output(['gcc', '-E', path])
#        token_stream = tokenize(headers)
#    except Exception, error:
#        print error
#    else:
#        print "success", path
#logs.close()
