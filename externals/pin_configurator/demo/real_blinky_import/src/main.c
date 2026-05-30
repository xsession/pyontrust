#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define LED0_NODE DT_ALIAS(led0)
#define SLEEP_TIME_MS 1000

#if DT_NODE_HAS_STATUS(LED0_NODE, okay)
static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(LED0_NODE, gpios);
#endif

int main(void)
{
    printk("Pin Configurator demo boot\n");

#if DT_NODE_HAS_STATUS(LED0_NODE, okay)
    if (!gpio_is_ready_dt(&led)) {
        printk("LED0 not ready\n");
    } else if (gpio_pin_configure_dt(&led, GPIO_OUTPUT_ACTIVE) < 0) {
        printk("LED0 configure failed\n");
    }
#endif

    while (1) {
#if DT_NODE_HAS_STATUS(LED0_NODE, okay)
        gpio_pin_toggle_dt(&led);
#endif
        printk("Blink\n");
        k_msleep(SLEEP_TIME_MS);
    }

    return 0;
}