import parser, re, json, sys
from translator import Translator, is_function

def rename_type(name):
    return re.sub(r"^Shake_|^SHAKE_", r"", name)

env = parser.default_env()
# Pass the path to shake.h to this code as an argument.
parser.parse(env, sys.argv[1:]) 
translate = Translator(env, rename_type)

constants = {}
variables = {}

for name, value in env.constants.iteritems():
    if re.match(r'^SHAKE_\w', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^SHAKE_", r"", name)
            constants[name] = value

for cname in env.names:
    if re.match(r'^Shake_\w', cname):
        typespec = translate.declarator(env.names[cname])
        name = re.sub(r"^Shake_", r"", cname)
        variables[name] = {'name':cname, 'type':typespec}

print json.dumps({
    'constants': constants,
    'types': translate.types,
    'variables': variables}, indent=2, sort_keys=True)
