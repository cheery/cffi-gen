import parser, re, json
from translator import Translator, is_function

def rename_type(name):
    return re.sub(r"^ovr", r"", name)

env = parser.default_env()
parser.parse(env, ['libOVR.h'],
    extra_flags=[
        "-I./OculusSDK/LibOVR/Include",
    ])
translate = Translator(env, rename_type)
translate.blacklist.update([
#    '_IO_marker',
#    '_IO_FILE',
])
translate.bluelist.update({
})

constants = {}
variables = {}

for name, value in env.constants.iteritems():
    if re.match(r'^OVR_\w', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^OVR_", r"", name)
            constants[name] = value
    if re.match(r'^ovr\w', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^ovr", r"", name)
            constants[name] = value

for cname in env.names:
    if re.match(r'^ovr_\w', cname):
        typespec = translate.declarator(env.names[cname])
        name = re.sub(r"^ovr_", r"", cname)
        variables[name] = {'name':cname, 'type':typespec}

print json.dumps({
    'constants': constants,
    'types': translate.types,
    'variables': variables}, indent=2, sort_keys=True)
