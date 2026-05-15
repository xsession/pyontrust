#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "generated_project_summary.h"

int main(void)
{
	printk("Pin Configurator demo boot\n");
	printk("Board: %s\n", PINCFG_DEMO_BOARD);
	printk("Pins configured: %d\n", PINCFG_DEMO_PIN_COUNT);
	printk("Enabled peripherals: %s\n", PINCFG_DEMO_ENABLED_PERIPHERALS);
	printk("Selected external devices: %s\n", PINCFG_DEMO_SELECTED_DEVICES);
	while (1) {
		k_msleep(1000);
	}
	return 0;
}
