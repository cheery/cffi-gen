import parser, re, json
from translator import Translator, is_function

def rename_type(name):
    return re.sub(r"^LLVM", r"", name)

env = parser.default_env()
parser.parse(env, [
    '-I./llvm6/include',
    './llvm6/include/llvm-c/Core.h',
    './llvm6/include/llvm-c/ExecutionEngine.h',
    './llvm6/include/llvm-c/Target.h',
    './llvm6/include/llvm-c/Analysis.h',
    './llvm6/include/llvm-c/BitWriter.h',
    ])
translate = Translator(env, rename_type)
translate.blacklist.update([
    'LLVMMCJITCompilerOptions'
])
translate.bluelist.update({
})

constants = {}
variables = {}

for name, value in env.constants.iteritems():
    if re.match(r'^LLVM\w', name):
        if isinstance(value, (int, str)):
            name = re.sub(r"^LLVM", r"", name)
            constants[name] = value

for cname in env.names:
    if re.match(r'^LLVM\w', cname):
        typespec = translate.declarator(env.names[cname])
        name = re.sub(r"^LLVM", r"", cname)
        variables[name] = {'name':cname, 'type':typespec}

print json.dumps({
    'comment': "Generated with https://github.com/cheery/cffi-gen",
    'constants': constants,
    'types': translate.types,
    'variables': variables}, indent=2, sort_keys=True)
