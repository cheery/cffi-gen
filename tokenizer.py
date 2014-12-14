keywords = set(
    "typedef char int short long unsigned signed struct static __inline inline __inline__ "
    "__restrict __extension__ __signed__ union volatile enum __asm__ double float "
    "sizeof extern __attribute__ const void __thread __restrict__".split(" "))
reserved = set()

class Stream(object):
    def __init__(self, source):
        self.source = source
        self.index  = 0
        self.lineno = 1

    @property
    def empty(self):
        return self.index >= len(self.source)

    @property
    def character(self):
        return self.source[self.index:self.index+1]

    @property
    def character_pair(self):
        return self.source[self.index:self.index+2]

    @property
    def character_tri(self):
        return self.source[self.index:self.index+3]

    def adv(self):
        ch = self.character
        self.index += 1
        if ch == '\n':
            self.lineno += 1
        return ch
    
def tokenize(source):
    stream = Stream(source)
    while not stream.empty:
        while not stream.empty and stream.character in ' \t\r\n':
            stream.adv()
        if stream.empty:
            continue
        if stream.character_pair == '/*':
            string = stream.adv() + stream.adv()
            while not stream.empty and stream.character_pair != '*/':
                string += stream.adv()
            string += stream.adv()
            string += stream.adv()
            continue
        if stream.character_pair == '//':
            string = stream.adv()
            while not stream.empty and stream.character != '\n':
                string += stream.adv()
            continue
        yield token(stream)

def token(stream):
    start = stream.index
    lineno = stream.lineno
    if stream.character == '#':
        string = stream.adv()
        while not stream.empty and stream.character != '\n':
            if stream.character == "\\":
                string += stream.adv()
            string += stream.adv()
        return lineno, 'MACRO', string
    if isnondigit(stream.character):
        string = stream.adv()
        while isnondigit(stream.character) or isdigit(stream.character):
            string += stream.adv()
        name = 'IDENTIFIER'
        if string in keywords:
            name = string.upper()
        elif string in reserved:
            name = 'RESERVED'
        elif string in ('true', 'false'):
            name = 'BOOLCONSTANT'
        return lineno, name, string
    if stream.character == '0' and stream.character_pair != '0.':
        string = stream.adv()
        if stream.character in ('x', 'X'):
            string += stream.adv()
            while ishex(stream.character):
                string += stream.adv()
            while stream.character.isalpha():
                stream.adv()
            return lineno, 'INTCONSTANT', int(string, 16)
        while isoctal(stream.character):
            string += stream.adv()
        while stream.character.isalpha():
            stream.adv()
        return lineno, 'INTCONSTANT', int(string, 8)
    if isdigit(stream.character):
        string = stream.adv()
        while isdigit(stream.character):
            string += stream.adv()
        cons = int
        name = 'INTCONSTANT'
        if stream.character == '.':
            cons = float
            name = 'FLOATCONSTANT'
            string += stream.adv()
            while isdigit(stream.character):
                string += stream.adv()
        if stream.character in ('e', 'E'):
            cons = float
            name = 'FLOATCONSTANT'
            string += stream.adv()
            if stream.character in ('-', '+'):
                string += stream.adv()
            if not isdigit(stream.character):
                raise Exception("expected digit %r" % string)
            string += stream.adv()
            while isdigit(stream.character):
                string += stream.adv()
        while stream.character.isalpha():
            stream.adv()
        return lineno, name, cons(string)
    if stream.character_tri in operators:
        string = stream.adv() + stream.adv() + stream.adv()
        return lineno, operators[string], string
    if stream.character_pair in operators:
        string = stream.adv() + stream.adv()
        return lineno, operators[string], string
    if stream.character in operators:
        string = stream.adv()
        return lineno, operators[string], string
    if stream.character == "'":
        stream.adv()
        string = ''
        if stream.character == "\\":
            string += parse_escape_sequence(stream)
        else:
            string += stream.adv()
        while stream.character != "'":
            string += stream.adv()
        stream.adv()
        return lineno, "CHARACTER", string
    if stream.character == '"':
        stream.adv()
        string = ''
        while stream.character != '"':
            if stream.character == "\\":
                string += parse_escape_sequence(stream)
            else:
                string += stream.adv()
        stream.adv()
        return lineno, "STRING", string
    raise Exception("invalid character %c" % stream.character)

def parse_escape_sequence(stream):
    assert stream.adv() == "\\"
    character = stream.adv()
    if character in escape_sequences:
        return escape_sequences[character]
    if isdigit(character):
        for k in range(2):
            if isdigit(stream.character):
                character += stream.adv()
        return chr(int(character, 8))
    if character == 'x':
        num = ''
        for k in range(2):
            if ishex(stream.character):
                num += stream.adv()
        return chr(int(num, 16))
    raise Exception("invalid escape sequence %c" % character)

# operator precedence table on page 40
operators = {
    "(":'LEFT_PAREN',
    ")":'RIGHT_PAREN',
    "[":'LEFT_BRACKET',
    "]":'RIGHT_BRACKET',
    "{":'LEFT_BRACE',
    "}":'RIGHT_BRACE',
    ".":'DOT',
    "++":'INC_OP',
    "--":'DEC_OP',
    ",":'COMMA',
    ":":'COLON',
    ";":'SEMICOLON',
    "+":'PLUS',
    "-":'DASH',
    "~":'BANG',
    "!":'TILDE',
    "*":'STAR',
    "/":'SLASH',
    "%":'PERCENT',
    "<<":'LEFT_OP',
    ">>":'RIGHT_OP',
    "<":'LEFT_ANGLE',
    ">":'RIGHT_ANGLE',
    "<=":'LE_OP',
    ">=":'GE_OP',
    "==":'EQ_OP',
    "!=":'NE_OP',
    "&":'AMPERSAND',
    "^":'CARET',
    "|":'VERTICAL_BAR',
    "&&":'AND_OP',
    "^^":'XOR_OP',
    "||":'OR_OP',
    "?":'QUESTION',
    "=":'EQUAL',
    "+=":'ADD_ASSIGN',
    "-=":'SUB_ASSIGN',
    "*=":'MUL_ASSIGN',
    "/=":'DIV_ASSIGN',
    "%=":'MOD_ASSIGN',
    "<<=":'LEFT_ASSIGN',
    ">>=":'RIGHT_ASSIGN',
    "&=":'AND_ASSIGN',
    "^=":'XOR_ASSIGN',
    "|=":'OR_ASSIGN',
}

escape_sequences = {
        'a': chr(0x07),
        'b': chr(0x08),
        'f': chr(0x0C),
        'n': chr(0x0A),
        'r': chr(0x0D),
        't': chr(0x09),
        'v': chr(0x0B),
        '\\': chr(0x5C),
        '\'': chr(0x27),
        '\"': chr(0x22),
        '?': chr(0x22),
}

def isnondigit(ch):
    return 'a' <= ch.lower() <= 'z' or ch == '_'

def ishex(ch):
    return 'a' <= ch.lower() <= 'f' or isdigit(ch)

def isoctal(ch):
    return '0' <= ch <= '7'

def isdigit(ch):
    return '0' <= ch <= '9'
