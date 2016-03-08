#!/usr/bin/python
# -*- coding:utf-8 -*-
import re

'''
简单的模板引擎，采用django模板语法，同时只实现了简单的部分:

    1、变量解析，支持解析字典的元素和类属性和类方法，支持管道符号”|“过滤处理变量
    2、简单逻辑处理，如 for循环和if处理


很多地方都没实现：

    1、模板继承和包含
    2、自定义标签
    3、自动过滤非法字符
    4、参数过滤
    5、复杂的逻辑，如elif 
    6、多个变量循环
    7、空白符控制

'''
class TempliteSyntaxError(ValueError):
    pass

class CodeBuilder(object):

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent
        self.INDENT_STEP = 4

    def add_line(self, line):
        self.code.extend([" " * self.indent_level, line, "\n"])

    def indent(self):
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        self.indent_level -= self.INDENT_STEP

    def add_section(self):
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        assert self.indent_level == 0
        python_source = str(self)
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace


class Templite(object):

    def __init__(self, text, *contexts):
        self.context = {}
        for context in contexts:
            self.context.update(context)
        #为了提高渲染出来的方法的执行速度，将所有变量放入self.all_vars中
        self.all_vars = set()
        self.loop_vars = set()

        code = CodeBuilder()
        code.add_line("def render_fuction(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered = []
        def flush_output():
            '''
            简化向code添加内容的过程，
            只需要向buffered添加，
            最后执行一下这个方法就可以把bufferedd的内容添加到code
            '''

            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) >1:
                code.add_line("extend_result(%s)" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []
        tokens = re.split(r"(?s)({{.*?}} | {%.*?%} | {#.*?#})", text)

        for token in tokens:
            if token.startswith('{#'):
                continue

            elif token.startswith('{{'):
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str(%s)") % expr

            elif token.startswith('{%'):
                flush_output()
                words = token[2:-2].strip().split()

                if words[0] == 'if':
                    if len(words) !=2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if %s:" % self._expr_code(words[1]))
                    code.indent()

                elif words[0] == 'for':
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append("for")
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                        "for c_%s in %s:" %(
                            words[1],
                            self._expr_code(words[3])
                            )
                        )

                elif words[0].startswith('end'):
                    if len(words) != 1:
                        self._syntax_error("Don't understand end",token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends",token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag",end_what)
                    code.dedent()

                else:
                    self._syntax_error("Don't understand tag",words[0])

            else:
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            self._syntax_error("Unmatched action tag",ops_stack[-1])

        flush_output()
        '''
        因为模板中所有使用到的变量都在all_vars中，
        而loop_vars中的变量都已经定义了，
        因为for循环中已经定义过了，
        所以这里要定义在all_vars中而不再loop_vars中的变量
        '''
        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

        code.add_line("return ''.join(result)")
        code.dedent()
        self._render_function = code.get_globals()['render_fuction']

    def _expr_code(self, expr):
        '''

        '''

        if "|" in expr:
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        elif "." in expr:
            pipes = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" %  (code, args)
        else:
            self._variable(expr, self.all_vars)
            code = "c_%s" % expr
        return code

    def _syntax_error(self, msg, thing):

        raise TempliteSyntaxError("%s: %r" % (msg, thing))

    def _variable(self, name, vars_set):
        '''
        检查变量命名，同时将变量加入self.all_vars或者self.loop_vars中
        '''
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", name):
            self._syntax_error("Not a valid name", name)
        vars_set.add(name)

    def render(self, context = None):

        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)

    def _do_dots(self, value, *dots):

        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[0]
            if callale(value):
                value = value()
        return value


# Make a Templite object.
templite = Templite('''
    <h1>Hello {{name|upper}}!</h1>
    {% for topic in topics %}
        <p>You are interested in {{topic}}.</p>
    {% endfor %}
    ''',
    {'upper': str.upper},
)

# Later, use it to render some data.
text = templite.render({
    'name': "Ned",
    'topics': ['Python', 'Geometry', 'Juggling'],
})
print text