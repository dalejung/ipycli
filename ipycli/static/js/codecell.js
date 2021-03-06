//----------------------------------------------------------------------------
//  Copyright (C) 2008-2011  The IPython Development Team
//
//  Distributed under the terms of the BSD License.  The full license is in
//  the file COPYING, distributed as part of this software.
//----------------------------------------------------------------------------

//============================================================================
// CodeCell
//============================================================================

var IPython = (function (IPython) {
    "use strict";

    var utils = IPython.utils;
    var key   = IPython.utils.keycodes;

    var CodeCell = function (kernel, notebook) {
        // The kernel doesn't have to be set at creation time, in that case
        // it will be null and set_kernel has to be called later.
        this.kernel = kernel || null;
        this.code_mirror = null;
        this.input_prompt_number = null;
        this.tooltip_on_tab = true;
        this.collapsed = false;
        IPython.Cell.apply(this, [notebook]);
    };


    CodeCell.prototype = new IPython.Cell();


    CodeCell.prototype.create_element = function () {
        var cell =  $('<div></div>').addClass('cell border-box-sizing code_cell vbox');
        cell.attr('tabindex','2');
        var input = $('<div></div>').addClass('input hbox');
        input.append($('<div/>').addClass('prompt input_prompt'));
        var input_area = $('<div/>').addClass('input_area box-flex1');
        var options = {
            indentUnit : 4,
            mode: 'python',
            theme: 'ipython',
            readOnly: this.read_only,
            onKeyEvent: $.proxy(this.handle_codemirror_keyevent,this)
        };
        var keyMap = this.notebook ? this.notebook.keyMap : null;
        if (keyMap){
          options['keyMap'] = keyMap;
        }
        this.code_mirror = CodeMirror(input_area.get(0), options);
        input.append(input_area);
        var output = $('<div></div>');
        cell.append(input).append(output);
        this.element = cell;
        this.output_area = new IPython.OutputArea(output, true);

        // construct a completer only if class exist
        // otherwise no print view
        if (IPython.Completer !== undefined)
        {
            this.completer = new IPython.Completer(this);
        }
    };

    CodeCell.prototype.handle_codemirror_keyevent = function (editor, event) {
        var ret = this._handle_codemirror_keyevent(editor, event);
        if (ret != null){
          return ret;
        }
        return false;
    },

    CodeCell.prototype._handle_codemirror_keyevent = function (editor, event) {
        // This method gets called in CodeMirror's onKeyDown/onKeyPress
        // handlers and is used to provide custom key handling. Its return
        // value is used to determine if CodeMirror should ignore the event:
        // true = ignore, false = don't ignore.

        if (this.read_only){
            return false;
        }

        var that = this;
        // whatever key is pressed, first, cancel the tooltip request before
        // they are sent, and remove tooltip if any, except for tab again
        if (event.type === 'keydown' && event.which != key.TAB ) {
            IPython.tooltip.remove_and_cancel_tooltip();
        };

        var cur = editor.getCursor();

        if (event.keyCode === key.ENTER && (event.shiftKey || event.ctrlKey)) {
            // Always ignore shift-enter in CodeMirror as we handle it.
            return true;
        } else if (event.which === 40 && event.type === 'keypress' && IPython.tooltip.time_before_tooltip >= 0) {
            // triger on keypress (!) otherwise inconsistent event.which depending on plateform
            // browser and keyboard layout !
            // Pressing '(' , request tooltip, don't forget to reappend it
            IPython.tooltip.pending(that);
        } else if (event.which === key.UPARROW && event.type === 'keydown') {
            // If we are not at the top, let CM handle the up arrow and
            // prevent the global keydown handler from handling it.
            if (!that.at_top()) {
                event.stop();
                return false;
            } else {
                return true;
            };
        } 
        /*
         * Had to remove from here to support vim
        else if (event.which === key.ESC) {
            IPython.tooltip.remove_and_cancel_tooltip(true);
            return true;
        } 
        */
        else if (event.which === key.DOWNARROW && event.type === 'keydown') {
            // If we are not at the bottom, let CM handle the down arrow and
            // prevent the global keydown handler from handling it.
            if (!that.at_bottom()) {
                event.stop();
                return false;
            } else {
                return true;
            };
        } else if (event.keyCode === key.TAB && event.type == 'keydown') {
            // Tab completion.
            //Do not trim here because of tooltip
            var pre_cursor = editor.getRange({line:cur.line,ch:0},cur);
            if (pre_cursor.trim() === "") {
                // Don't autocomplete if the part of the line before the cursor
                // is empty.  In this case, let CodeMirror handle indentation.
                return false;
            } else if ((pre_cursor.substr(-1) === "("|| pre_cursor.substr(-1) === " ") && that.tooltip_on_tab ) {
                IPython.tooltip.request(that);
                // Prevent the event from bubbling up.
                event.stop();
                // Prevent CodeMirror from handling the tab.
                return true;
            } else {
                event.stop();
                this.completer.startCompletion();
                return true;
            };
        } else if (event.keyCode === key.BACKSPACE && event.type == 'keydown') {
            // If backspace and the line ends with 4 spaces, remove them.
            var line = editor.getLine(cur.line);
            var ending = line.slice(-4);
            if (ending === '    ') {
                editor.replaceRange('',
                    {line: cur.line, ch: cur.ch-4},
                    {line: cur.line, ch: cur.ch}
                );
                event.stop();
                return true;
            } else {
                return false;
            };
        } else {
            // keypress/keyup also trigger on TAB press, and we don't want to
            // use those to disable tab completion.
            return null;
        };
        return null;
    };


    // Kernel related calls.

    CodeCell.prototype.set_kernel = function (kernel) {
        this.kernel = kernel;
    }


    CodeCell.prototype.execute = function () {
        var code = this.get_code();
        if(code.search('%cell_func') == 0) {
            return this.cell_func()
        }
        this.output_area.clear_output(true, true, true);
        this.set_input_prompt('*');
        this.element.addClass("running");
        var callbacks = {
            'execute_reply': $.proxy(this._handle_execute_reply, this),
            'output': $.proxy(this.output_area.handle_output, this.output_area),
            'clear_output': $.proxy(this.output_area.handle_clear_output, this.output_area),
            'set_next_input': $.proxy(this._handle_set_next_input, this)
        };
        var msg_id = this.kernel.execute(code, callbacks, {silent: false});
    };

    CodeCell.prototype.cell_func = function () {
        this.output_area.clear_output(true, true, true);
        this.set_input_prompt('*');
        this.element.addClass("running");
        var settings = {
            processData : false,
            cache : false,
            type : "GET",
            dataType : "json",
            success : $.proxy(this.run_cell_func,this),
        };
        var lines = this.get_code().split('\n');
        var first_line = lines[0];
        var bits = first_line.split(' ');
        var func_name = bits[1];
        var kernel_id = this.kernel.kernel_id;
        var url = $('body').data('baseProjectUrl') + 'cell_func';
        url = url + '/' + kernel_id;
        url = url + '/' + func_name;
        $.ajax(url, settings);
    };    

    CodeCell.prototype.run_cell_func = function (data, status, xhr) {
        data = '('+data+')';
        data = eval(data);
        var filepath = data['file'];
        var source = data['source'];
        var lines = this.get_code().split('\n');
        var new_lines = [lines[0], '# '+filepath];
        new_lines = new_lines.concat(source.split('\n'));
        var new_body = new_lines.join('\n');
        this.set_text(new_body);

        var callbacks = {
            'execute_reply': $.proxy(this._handle_execute_reply, this),
            'output': $.proxy(this.output_area.handle_output, this.output_area),
            'clear_output': $.proxy(this.output_area.handle_clear_output, this.output_area),
            'set_next_input': $.proxy(this._handle_set_next_input, this)
        };
        var msg_id = this.kernel.execute(source, callbacks, {silent: false});
    };


    CodeCell.prototype._handle_execute_reply = function (content) {
        this.set_input_prompt(content.execution_count);
        this.element.removeClass("running");
        $([IPython.events]).trigger('set_dirty.Notebook', {'value': true});
    }

    CodeCell.prototype._handle_set_next_input = function (text) {
        var data = {'cell': this, 'text': text}
        $([IPython.events]).trigger('set_next_input.Notebook', data);
    }

    // Basic cell manipulation.

    CodeCell.prototype.select = function () {
        IPython.Cell.prototype.select.apply(this);
        this.code_mirror.refresh();
        this.code_mirror.focus();
        // We used to need an additional refresh() after the focus, but
        // it appears that this has been fixed in CM. This bug would show
        // up on FF when a newly loaded markdown cell was edited.
    };


    CodeCell.prototype.select_all = function () {
        var start = {line: 0, ch: 0};
        var nlines = this.code_mirror.lineCount();
        var last_line = this.code_mirror.getLine(nlines-1);
        var end = {line: nlines-1, ch: last_line.length};
        this.code_mirror.setSelection(start, end);
    };


    CodeCell.prototype.collapse = function () {
        this.collapsed = true;
        this.output_area.collapse();
    };


    CodeCell.prototype.expand = function () {
        this.collapsed = false;
        this.output_area.expand();
    };


    CodeCell.prototype.toggle_output = function () {
        this.collapsed = Boolean(1 - this.collapsed);
        this.output_area.toggle_output();
    };


    CodeCell.prototype.toggle_output_scroll = function () {
    this.output_area.toggle_scroll();
    };


    CodeCell.prototype.set_input_prompt = function (number) {
        this.input_prompt_number = number;
        var ns = number || "&nbsp;";
        this.element.find('div.input_prompt').html('In&nbsp;[' + ns + ']:');
    };


    CodeCell.prototype.clear_input = function () {
        this.code_mirror.setValue('');
    };

    CodeCell.prototype.get_code = function () {
      /*
        Separate out code/text so we can do things like parse the code before
        send to execute
      */
      var cell = this;
        var code = cell.get_text();
        var lines = code.split("\n");
        var result = [];
        for(var i=0; i < lines.length; i++) {
          var line = lines[i];
          if (line == '# stop') {
            break
          }
          result.push(line);
        }
        var codeText = result.join("\n");
        return codeText;
    };

    CodeCell.prototype.get_text = function () {
        return this.code_mirror.getValue();
    };


    CodeCell.prototype.set_text = function (code) {
        return this.code_mirror.setValue(code);
    };


    CodeCell.prototype.at_top = function () {
        var cursor = this.code_mirror.getCursor();
        if (cursor.line === 0) {
            return true;
        } else {
            return false;
        }
    };


    CodeCell.prototype.at_bottom = function () {
        var cursor = this.code_mirror.getCursor();
        if (cursor.line === (this.code_mirror.lineCount()-1)) {
            return true;
        } else {
            return false;
        }
    };


    CodeCell.prototype.clear_output = function (stdout, stderr, other) {
        this.output_area.clear_output(stdout, stderr, other);
    };


    // JSON serialization

    CodeCell.prototype.fromJSON = function (data) {
        IPython.Cell.prototype.fromJSON.apply(this, arguments);
        if (data.cell_type === 'code') {
            if (data.input !== undefined) {
                this.set_text(data.input);
                // make this value the starting point, so that we can only undo
                // to this state, instead of a blank cell
                this.code_mirror.clearHistory();
            }
            if (data.prompt_number !== undefined) {
                this.set_input_prompt(data.prompt_number);
            } else {
                this.set_input_prompt();
            };
            this.output_area.fromJSON(data.outputs);
            if (data.collapsed !== undefined) {
                if (data.collapsed) {
                    this.collapse();
                } else {
                    this.expand();
                };
            };
        };
    };


    CodeCell.prototype.toJSON = function () {
        var data = IPython.Cell.prototype.toJSON.apply(this);
        data.input = this.get_text();
        data.cell_type = 'code';
        if (this.input_prompt_number) {
            data.prompt_number = this.input_prompt_number;
        };
        var outputs = this.output_area.toJSON();
        data.outputs = outputs;
        data.language = 'python';
        data.collapsed = this.collapsed;
        return data;
    };


    IPython.CodeCell = CodeCell;

    return IPython;
}(IPython));
