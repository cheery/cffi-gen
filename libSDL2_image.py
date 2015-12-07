import parser, re, json
from translator import Translator, is_function

def rename_type(name):
    assert not name.startswith("SDL_"), name
    return re.sub(r"^IMG_", r"", name)

def dependency(name):
    if name.startswith("SDL_"):
        return "libSDL2." + re.sub(r"^SDL_", r"", name)

env = parser.default_env()
parser.parse(env, ['/usr/include/SDL2/SDL_image.h'])
translate = Translator(env, rename_type, dependency)
translate.blacklist.update([
])
translate.bluelist.update({
})

constants = {}
variables = {}

for name, value in env.constants.iteritems():
    if re.match(r'^IMG_\w', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^IMG_", r"", name)
            constants[name] = value

for cname in env.names:
    if re.match(r'^IMG_\w', cname):
        typespec = translate.declarator(env.names[cname])
        name = re.sub(r"^IMG_", r"", cname)
        variables[name] = {'name':cname, 'type':typespec}

print json.dumps({
    'constants': constants,
    'depends': ["libSDL2"],
    'types': translate.types,
    'variables': variables}, indent=2, sort_keys=True)
