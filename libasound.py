import parser, re, json
from translator import Translator, is_function

def rename_type(name):
    return re.sub(r"^snd_", r"", name)

env = parser.default_env()
parser.parse(env, ['/usr/include/alsa/asoundlib.h'])
translate = Translator(env, rename_type)
translate.blacklist.update([
    'pollfd', # recursive rule
    '_IO_marker', # recursive rule
    '_IO_FILE', # recursive rule
])
translate.bluelist.update({
    'snd_seq_real_time': 'seq_real_time',
    'snd_dlsym_link': 'dlsym_link',
})

constants = {}
functions = {}
variables = {}

for name, value in env.constants.iteritems():
    if re.match(r'^SND_\w', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^SND_", r"", name)
            constants[name] = value

for name in env.names:
    if re.match(r'^snd_\w', name):
        typespec = translate.declarator(env.names[name])
        name = re.sub(r"^snd_", r"", name)
        if is_function(typespec):
            functions[name] = typespec
        else:
            variables[name] = typespec

print json.dumps({
    'constants': constants,
    'functions': functions,
    'types': translate.types,
    'variables': variables}, indent=2, sort_keys=True)
