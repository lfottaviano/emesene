# -*- coding: utf-8 -*-

#    This file is part of emesene.
#
#    emesene is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    emesene is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with emesene; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gtk

import gui
import e3
import extension

import sys
import logging

log = logging.getLogger('gtkui.MainWindow')


class MainWindow(gtk.VBox, gui.MainWindowBase):
    '''this class represents the widget that is shown when the user is logged
    in (menu, contact list etc)'''
    NAME = 'Main Window'
    DESCRIPTION = 'The window used when an account is logged in'
    AUTHOR = 'Mariano Guerra'
    WEBSITE = 'www.emesene.org'

    def __init__(self, session, on_new_conversation):
        '''class constructor'''
        gtk.VBox.__init__(self)
        gui.MainWindowBase.__init__(self, session, on_new_conversation)

        UserPanel = extension.get_default('user panel')
        ContactList = extension.get_default('contact list')

        self.below_menu = extension.get_and_instantiate('below menu', self)
        self.below_panel = extension.get_and_instantiate('below panel', self)
        self.below_userlist = extension.get_and_instantiate('below userlist',
                                                            self)

        self.contact_list = ContactList(session)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.set_border_width(1)

        self.session.signals.contact_attr_changed.subscribe(
            self._on_contact_attr_changed)
        self.session.signals.close.subscribe(self.on_disconnect)

        self.menu = None
        self.contact_menu = None
        self.group_menu = None

        self._build_menus()

        self.panel = UserPanel(session)
        self.panel.nick.connect('text-changed', self._on_nick_changed)
        self.panel.message.connect('text-changed', self._on_message_changed)
        self.panel.mail.connect('button_release_event', self._on_mail_click)
        self.panel.search.connect('toggled', self._on_search_toggled)
        self.panel.enabled = False

        self.entry = gtk.Entry()
        if hasattr(gtk.Entry, "set_placeholder_text"):
            self.entry.set_placeholder_text(_('Type to search...'))
        self.entry.connect('changed', self._on_entry_changed)
        self.entry.connect('key-press-event', self._on_entry_key_press)

        self.pack_start(self.menu, False)
        self.pack_start(self.below_menu, False)
        self.pack_start(self.panel, False)
        self.pack_start(self.below_panel, False)
        self.pack_start(self.entry, False)
        self.pack_start(scroll, True, True)
        self.pack_start(self.below_userlist, False)

        self.contact_list.contact_selected.subscribe(self._on_contact_selected)
        self.contact_list.group_selected.subscribe(self._on_group_selected)
        self.contact_list.contact_menu_selected.subscribe(
            self._on_contact_menu_selected)

        if self.session.session_has_service(e3.Session.SERVICE_GROUP_MANAGING):
            self.contact_list.group_menu_selected.subscribe(
                self._on_group_menu_selected)

        scroll.add(self.contact_list)
        scroll.show_all()

        self.session.config.subscribe(self._on_show_userpanel_changed,
            'b_show_userpanel')
        self.session.config.subscribe(self._on_show_mail_inbox_changed,
            'b_show_mail_inbox')

        self._on_show_userpanel_changed(self.session.config.b_show_userpanel)
        self._on_show_mail_inbox_changed(self.session.config.b_show_mail_inbox)

    def _on_mail_count_changed(self, count):
        self.panel.mail.set_label("(%d)" % count)

    def _on_mail_click(self, widget, event):
        if event.button == 1:
            self.on_mail_click()

    def _on_social_request(self, conn_url):

        def get_token(token_url):
            '''strips the access token from an url'''
            if token_url is None:
                return token_url

            if token_url.find("#access_token=") == -1:
                return None

            pattern_start_token = "#access_token="
            pattern_end_token = "&expires_in"
            start_token = token_url.find(pattern_start_token) + len(pattern_start_token)
            end_token = token_url.find(pattern_end_token)
            return token_url[start_token:end_token]

        def set_token(token_url):
            '''callback used by webkit'''
            self.session.config.facebook_token = get_token(token_url)
            #only activate service if we have an access token
            activate = bool(self.session.config.facebook_token is not None)
            self.session.activate_social_services(activate)

        def set_token_fallback(response, data, token_url):
            '''callback used as fallback when webkit isn't avariable'''
            self.session.config.facebook_token = get_token(token_url)
            #only activate service if user press accept and we have an access token
            activate = bool(response == 1 and self.session.config.facebook_token is not None)
            self.session.activate_social_services(activate)

        dialog = extension.get_default('dialog')

        use_fallback = (gui.gtkui.WEBKITERROR or sys.platform == 'darwin' or
                        #FIXME: remove this check when webkit works on windows 7
                        (sys.platform == 'win32' and sys.getwindowsversion()[0] > 6))

        if not use_fallback:
            dialog.web_window(_("Connect Emesene and Facebook"),
                              conn_url, set_token)
        else:
            #Fallback method
            #Open a browser and ask user to copy the access token
            gui.base.Desktop.open(conn_url)
            w = dialog.entry_window("Url:", "", set_token_fallback, "Facebook Integration", None)
            lbl = dialog.window_add_label_vbox(w,
                  _("Please login into facebook and copy the url opened in your browser here"))
            lbl.set_selectable(False)
            w.vbox.reorder_child(lbl, 0)
            w.show()

    def _on_show_userpanel_changed(self, value):
        '''callback called when config.b_show_userpanel changes'''
        if value:
            self.panel.show()
        else:
            self.panel.hide()
        self._on_show_mail_inbox_changed(self.session.config.b_show_mail_inbox)

    def _on_show_mail_inbox_changed(self, value):
        '''callback called when config.b_show_mail_inbox changes'''
        self.panel.mail.set_visible(value)

    def _build_menus(self):
        '''buildall the menus used on the client'''

        handler = gui.base.MenuHandler(self.session, self.contact_list)

        contact_handler = gui.base.ContactHandler(self.session,
            self.contact_list)

        MainMenu = extension.get_default('main menu')
        ContactMenu = extension.get_default('menu contact')

        self.menu = MainMenu(handler, self.session)

        self.contact_menu = ContactMenu(contact_handler, self.session)
        self.contact_menu.show_all()
        if self.session.session_has_service(e3.Session.SERVICE_GROUP_MANAGING):
            group_handler = gui.base.GroupHandler(self.session,
                self.contact_list)
            GroupMenu = extension.get_default('menu group')
            self.group_menu = GroupMenu(group_handler)
            self.group_menu.show_all()
            
    def destroy_all(self):
        print "Destroying all...",  self
        self.menu.destroy_children()
        self.menu.destroy()
        self.below_menu.destroy()
        self.below_panel.destroy()
        self.below_userlist.destroy()
        del self.menu
        del self.below_menu
        del self.below_panel
        del self.below_userlist
        self.contact_list.destroy_all()
        self.contact_list.destroy()
        del self.contact_list


    def set_accels(self):
        ''' set accels group to the given window '''
        accel_group = gtk.AccelGroup()
        self.get_parent().add_accel_group(accel_group)
        self.get_parent().accel_group = accel_group
        self.menu.set_accels(accel_group)
        accel_group.connect_group(gtk.keysyms.F,
                                  gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED,
                                  self.on_key_search)
        accel_group.connect_group(gtk.keysyms.Escape,
                                  0, gtk.ACCEL_LOCKED,
                                  self.on_key_hide)

    def on_key_hide(self, accel_group, window, keyval, modifier):
        '''Catches Escape and closes the window'''
        if self.panel.search.get_active():
            return

        self.get_parent().emit('delete-event', gtk.gdk.Event(gtk.gdk.DELETE))

    def on_key_search(self, accel_group, window, keyval, modifier):
        '''Catches Ctrl+F and opens or closes the search entry'''
        self.panel.search.set_active(not self.panel.search.get_active())
        if self.panel.search.get_active():
            self.entry.show()
            self.entry.grab_focus()
        else:
            self.entry.hide()

    def show(self):
        '''show the widget'''
        gtk.VBox.show(self)
        if not self.session.config.b_hide_menu:
            self.menu.show_all()
        self.contact_list.show()
        self.below_menu.show()
        self.below_panel.show()
        self.below_userlist.show()
        self.contact_list._set_accels(self.get_parent())

    def _replace_below_userlist(self):
        self.remove(self.below_userlist)
        self.below_userlist = extension.get_and_instantiate('below userlist', self)
        self.pack_start(self.below_userlist, False)
        pos = len(self.get_children()) - 1
        self.reorder_child(self.below_userlist, pos)
        self.below_userlist.show()

    def _replace_below_menu(self):
        self.remove(self.below_menu)
        self.below_menu = extension.get_and_instantiate('below menu', self)
        self.pack_start(self.below_menu, False)
        self.reorder_child(self.below_menu, 1)
        self.below_menu.show()

    def _replace_below_panel(self):
        self.remove(self.below_panel)
        self.below_panel = extension.get_and_instantiate('below panel', self)
        self.pack_start(self.below_panel, False)
        self.reorder_child(self.below_panel, 3)
        self.below_panel.show()

    def replace_extensions(self):
        self._replace_below_userlist()
        self._replace_below_menu()
        self._replace_below_panel()
        self.panel.replace_userpanel_extension(self)

    def _on_entry_changed(self, entry, *args):
        '''called when the text on entry changes'''
        self.contact_list.filter_text = entry.get_text().lower()
        self.contact_list.expand_groups()
        self.contact_list.select_top_contact()

    def _on_entry_key_press(self, entry, event):
        '''called when a key is pressed on the search box'''
        if event.keyval == gtk.keysyms.Escape:
            self.panel.search.set_active(False)
            entry.hide()

    def _on_contact_selected(self, contact):
        '''callback for the contact-selected signal'''
        self.on_new_conversation_requested(contact.account)

    def _on_group_selected(self, group):
        '''callback for the group-selected signal'''
        pass

    def _on_contact_menu_selected(self, contact):
        '''callback for the contact-menu-selected signal'''
        if contact.blocked:
            self.contact_menu.set_blocked()
        else:
            self.contact_menu.set_unblocked()
        self.contact_menu.popup(None, None, None, 0, 0)

    def _on_group_menu_selected(self, group):
        '''callback for the group-menu-selected signal'''
        if self.contact_list.is_favorite_group_selected():
            self.group_menu.show_unset_favorite_item()
        else:
            self.group_menu.show_set_favorite_item()
        self.group_menu.popup(None, None, None, 0, 0)

    def _on_contact_attr_changed(self, account, change_type, old_value,
            do_notify=True):
        '''callback called when an attribute of a contact changed'''
        contact = self.session.contacts.get(account)
        if not contact:
            log.debug('account %s not found on contacts' % account)

    def _on_nick_changed(self, textfield, old_text, new_text):
        '''method called when the nick is changed on the panel'''
        self.session.set_nick(new_text)

    def _on_message_changed(self, textfield, old_text, new_text):
        '''method called when the nick is changed on the panel'''
        self.session.set_message(new_text)

    def _on_key_press(self, widget, event):
        '''method called when a key is pressed on the input widget'''
        if (event.keyval == gtk.keysyms.Return or \
            event.keyval == gtk.keysyms.KP_Enter) and \
           self.panel.search.get_active():
            self.contact_list.open_conversation()
            self.panel.search.set_active(False)
            return

        if event.state & gtk.gdk.CONTROL_MASK or \
           event.keyval == gtk.keysyms.Return or \
           event.keyval == gtk.keysyms.KP_Enter or \
           event.keyval == gtk.keysyms.Escape:
            return

        if not self.panel.nick.has_focus() and \
           not self.panel.message.has_focus():
            if event.string != "" and not self.panel.search.get_active():
                    self.panel.search.set_active(True)
            elif event.keyval == gtk.keysyms.BackSpace and \
                 self.entry.get_text_length() == 1:
                self.panel.search.set_active(False)

    def on_disconnect(self, close=None):
        '''callback called when the disconnect option is selected'''
        gui.MainWindowBase.on_disconnect(self)
        self.contact_list.contact_selected.unsubscribe(
            self._on_contact_selected)
        self.contact_list.group_selected.unsubscribe(self._on_group_selected)
        self.contact_list.contact_menu_selected.unsubscribe(
            self._on_contact_menu_selected)

        if self.session.session_has_service(e3.Session.SERVICE_GROUP_MANAGING):
            self.contact_list.group_menu_selected.unsubscribe(
                self._on_group_menu_selected)
        self.contact_list.remove_subscriptions()
        self.session.config.unsubscribe(self._on_show_userpanel_changed,
            'b_show_userpanel')
        self.session.config.unsubscribe(self._on_show_mail_inbox_changed,
            'b_show_mail_inbox')
        self.session.signals.contact_attr_changed.unsubscribe(
            self._on_contact_attr_changed)
        self.panel.remove_subscriptions()
        self.session.signals.close.unsubscribe(self.on_disconnect)

    def _on_search_toggled(self, button):
        '''called when the search button is toggled'''
        if button.get_active():
            self.entry.show()
            self.entry.grab_focus()
            self.contact_list.is_searching = True
            # Using private member because i don't want to update config
            self.contact_list._show_empty_groups = True
            self.contact_list.refilter()
        else:
            self.entry.set_text('')
            self.entry.hide()
            self.contact_list.is_searching = False
            self.contact_list.show_empty_groups = self.session.config.b_show_empty_groups
            self.contact_list.un_expand_groups()
