---
title: Support and FAQ
slug: faq
description: Answers to common questions about Virtual Church Musician, plus where to find guides and how to reach us.
---
Answers to common questions about Virtual Church Musician. The [User Manual and System Administrator Guide](download.html#documentation) are on the Download page. There is a page of [training and demo videos](training.html) too. If you do not find your answer here, [contact us](contact.html). We reply by email, usually within 5 to 10 business days.

## Which apps are free, and which are paid?

VCM Templates, VCM Services, VCM Runner, VCM Administrator, and VCM Security are free to download. They connect to your church's VCM Server, which, like the VCM MIDI Player, is a paid product.

## Can I try it before buying?

Yes. Every app has a **Try the Demo** button that runs it with no Server at all, against a small set of built-in sample data: a "Demo" hymnal with 14 hymns, 4 chants, 2 service templates, and 2 published services. An orange DEMO MODE banner stays on screen, nothing is sent over the network, and changes are discarded when you close the app. No music plays in demo mode -- VCM Runner shows an item moving through its playback states, but produces no sound and sends no MIDI -- so there is no audio hardware to set up. Close the app and open it again to leave the demo.

## Do the free apps need the Server?

Yes. The apps connect over your church's network to the VCM Server, which stores your hymnals, hymns, chants, templates, and services and plays the music at the right moment.

## What does it play?

The Server plays MP3 recordings as stereo audio through your sound system, and it can send MIDI files to a MIDI instrument such as an organ or keyboard. If the instrument is connected to the Server, the Server sends the MIDI directly. If it is not, a VCM MIDI Player placed next to the instrument receives the file over your church network and plays it.

## Does it need an internet connection or an account?

No. The apps work without an internet connection, and the Server can run on a fully air-gapped network. The apps do not require an account with us.

## What information do you collect?

The apps send nothing to us. See the [Privacy Policy](privacy.html) for the details, including what this website does and does not collect.

## Which computers and devices are supported?

The desktop apps run on Windows, macOS, and Linux. The VCM Server and VCM MIDI Player also run on the Raspberry Pi 4 and Raspberry Pi 5 (64-bit). The Android apps for on-the-go use are provided as APK files you download from this site, and Google Play listings are planned. There is no iPhone or iPad version yet.

## How do I install an Android app from an APK?

Open the downloaded file. If Android asks, allow your browser or Files app to install unknown apps, and choose to install anyway if Android shows a Play Protect notice. The [Download page](download.html#installing) has the details.

## How do I get my hymnals into the system?

Hymnals, seasons, categories, hymns, chants, and service templates are brought in as definitions, using Import Hymn and Chant Definitions in the VCM Administrator. The MP3 and MIDI music files are loaded separately with Load Music Files, and a Mega Bundle brings in both in one step. We can help you plan and build your hymnal metadata definitions; see [Services](services.html).

## Do I need the rights to the music I load?

Yes. You are responsible for having the rights to the music files and other content you load into the system. We do not supply copyrighted music.

## How do I buy the VCM Server and the VCM MIDI Player?

The paid products will be sold through an online sales platform. Purchase details will be posted on the Download page before the first public release. Questions in the meantime: [contact us](contact.html).

## What is your refund policy?

You may request a refund within {{refund_days}} days after purchase, provided you have stopped using the software and removed all copies. Write to inquiries@kng-consulting.com. The [License Agreement](license.html) has the full terms. The refund policy covers software. Hardware orders are custom builds and are not refundable.

## On macOS, the app says it is damaged or cannot be opened. What do I do?

This means the app has not been notarized by Apple yet; nothing is actually wrong with it. Double-click the fix_app_permissions.command file included in the same download once, then open the app normally from your Applications folder.

## Can you customize Virtual Church Musician for our church?

Yes. KnG Consulting creates custom versions of Virtual Church Musician, and can brand and tailor editions for publishers. Customers cannot change the software themselves under the license, but we can. See [Services](services.html) and ask for a quote.

## Can you set up VCM Server or VCM MIDI Player hardware?

Yes, in either of two ways: a custom build that we sell you, or installation and configuration on hardware you supply. See [Services](services.html) and ask for a quote.

## What hardware do you recommend?

We recommend the Raspberry Pi 4 or Raspberry Pi 5 for both the VCM Server and the VCM MIDI Player, and the details are in [What Raspberry Pi hardware do you recommend?](#what-raspberry-pi-hardware-do-you-recommend). The VCM Server and VCM MIDI Player also run on Windows, macOS, and Linux computers.

## What Raspberry Pi hardware do you recommend?

This is our recommended hardware. It changes as new boards and interfaces appear, and we keep this answer up to date.

- **Board:** the Raspberry Pi 5 (preferred for new builds) or the Raspberry Pi 4. Older Pi models are not supported. The Pi 5 has no 3.5 mm audio jack.
- **Memory:** 4 GB or more is recommended. 2 GB works for the VCM Server, which is lightweight. 1 GB is not supported.
- **Operating system:** 64-bit Raspberry Pi OS Lite (no desktop needed). Install the VCM Server and VCM MIDI Player `.deb` packages on a standard install; there is no ready-made SD card or SSD image.
- **Storage:** an SSD is recommended, because the VCM Server writes its database continuously and ordinary microSD cards wear out. A high-endurance microSD card from a reputable brand is acceptable. Avoid bargain or unbranded cards.
- **Power and cooling:** use the official Raspberry Pi power supply for your board (27 W for the Pi 5, 15 W for the Pi 4) and a case with cooling. Weak power causes dropouts, and a hot Pi glitches playback.
- **Audio out (VCM Server, MP3 playback):** a USB class-compliant audio interface, such as a Behringer UCA202 or UCA222 for basic stereo (RCA), or a Focusrite Scarlett Solo or 2i2 in class-compliant mode for balanced outputs. Do not rely on the Pi's built-in audio or HDMI audio.
- **MIDI out (VCM MIDI Player):** a plain USB class-compliant to 5-pin DIN MIDI interface, such as the Roland UM-ONE mk2, plus a MIDI cable to your sound module. The VCM MIDI Player only sends MIDI to real hardware and makes no sound itself. Avoid unbranded clone cables and any interface that needs a vendor driver.

Example builds:

- **VCM Server only:** Raspberry Pi 5 (4 GB or more), official power supply, cooled case, an SSD, and a USB audio interface.
- **VCM MIDI Player only:** Raspberry Pi 4 or 5 (2 GB or more), official power supply, cooled case, a high-endurance microSD card, and a USB MIDI interface with a cable to your sound module.
- **Both on one Pi:** combine the two lists and use a board with 4 GB or more.

Using your own Pi works the same way. Devices that are not on this list may work, but we have not verified them. If you would like us to supply and set up the hardware, see [Services](services.html).

## How do I get help?

Start with the [User Manual and System Administrator Guide](download.html#documentation). For anything else, use the [contact form](contact.html).

## Are there training videos?

Yes. The [Training page](training.html) will have short, captioned videos for each app, on a computer and on an Android phone or tablet, starting with how to connect to your church's Server. Each one has a written transcript. Some are still being made and are marked "Coming soon".
