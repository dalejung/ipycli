
old_handle_keyevent = IPython.CodeCell.prototype._handle_codemirror_keyevent ;
IPython.CodeCell.prototype._base_handle_codemirror_keyevent = old_handle_keyevent;

IPython.CodeCell.prototype.handle_codemirror_keyevent = function (editor, event) {
  var ret =  this._base_handle_codemirror_keyevent(editor, event);
  if(ret != null) {
    return ret;
  }
}
