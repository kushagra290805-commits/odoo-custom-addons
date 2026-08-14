/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class Dashboard extends Component {
    static template = "nexora_studio.Dashboard";
}

registry.category("actions").add("nexora_studio_dashboard", Dashboard);
