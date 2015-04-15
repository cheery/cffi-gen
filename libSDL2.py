import parser, re, json
from translator import Translator, is_function

def rename_type(name):
    return re.sub(r"^SDL_", r"", name)

env = parser.default_env()
parser.parse(env, ['/usr/include/SDL2/SDL.h'])
translate = Translator(env, rename_type)
translate.blacklist.update([
    '_IO_marker',
    '_IO_FILE',
])
translate.bluelist.update({
    'SDL_AudioCVT': 'AudioCVT_t',
    'SDL_assert_data': 'assert_data_t',
    'SDL_PixelFormat': 'PixelFormat_t',
    'SDL_RWops': 'RWops_t',
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
