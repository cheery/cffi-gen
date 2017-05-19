import parser, re, json
from translator import Translator, is_function

def rename_type(name):
    return re.sub(r"^SDL_", r"", name)

env = parser.default_env()
parser.parse(env, ['libSDL2.h'])
translate = Translator(env, rename_type)
translate.blacklist.update([
    '_IO_marker',
    '_IO_FILE',
])
translate.bluelist.update({
    'SDL_AudioCVT': 'AudioCVT',
    'SDL_assert_data': 'assert_data',
    'SDL_AssertData': 'AssertData',
    'SDL_PixelFormat': 'PixelFormat',
    'SDL_RWops': 'RWops',
})

constants = {}
variables = {}

for name, value in env.constants.iteritems():
    if re.match(r'^SDL_\w', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^SDL_", r"", name)
            constants[name] = value

for cname in env.names:
    if re.match(r'^SDL_\w', cname):
        typespec = translate.declarator(env.names[cname])
        name = re.sub(r"^SDL_", r"", cname)
        variables[name] = {'name':cname, 'type':typespec}

print json.dumps({
    'constants': constants,
    'types': translate.types,
    'variables': variables}, indent=2, sort_keys=True)
