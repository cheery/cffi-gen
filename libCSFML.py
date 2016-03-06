import parser, re, json
from translator import Translator, is_function

def rename_type(name):
    return re.sub(r"^sf", r"", name)

env = parser.default_env()
parser.parse(env, ['libCSFML.h'], extra_flags=["-I./CSFML-2.3/include/"])
translate = Translator(env, rename_type)
translate.blacklist.update([
])
translate.bluelist.update({
})

constants = {}
variables = {}

for name, value in env.constants.iteritems():
    if re.match(r'^sf', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^sf", r"", name)
            constants[name] = value

for cname in env.names:
    if re.match(r'^sf', cname):
        typespec = translate.declarator(env.names[cname])
        name = re.sub(r"^sf", r"", cname)
        variables[name] = {'name':cname, 'type':typespec}

print json.dumps({
    'constants': constants,
    'types': translate.types,
    'variables': variables}, indent=2, sort_keys=True)
