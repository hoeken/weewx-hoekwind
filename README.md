WeeWX Hoeken's LED Matrix - WeeWX extension that displays data on an LED matrix
=
Based in large part on the [WindGuru extension](https://github.com/claudobahn/weewx-windguru) written by Claud Obahn.

## Installation
1. Download the extension
    > wget wget -O weewx-hoekwind-matrix.zip https://github.com/hoeken/weewx-hoekwind/archive/master.zip

2. Run the extension installer:

   > wee_extension --install weewx-hoekwind-matrix.zip

3. Update weewx.conf:

    ```
    [StdRESTful]
        [[HoekWindLEDMatrix]]
    ```

4. Restart WeeWX

    > sudo /etc/init.d/weewx stop

    > sudo /etc/init.d/weewx start
