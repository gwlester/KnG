---
title: Help and troubleshooting
slug: findcache-help
order: 8
summary: Answers to common questions: GPS accuracy, the compass, Bluetooth sharing, maps, privacy and getting help.
description: Troubleshooting and answers to common questions about FindCache: GPS accuracy, compass calibration, Bluetooth sharing, offline maps and privacy.
---

## Why is the distance jumping around?

GPS wanders a few metres even when you stand still. Tap **Average my position** and stay put for a minute or two: the readings settle and the uncertainty radius shrinks. A clear view of the sky helps most. Trees, buildings, and standing indoors all make the fix worse. Also check that **High-accuracy GPS** is on in [Settings](findcache-settings.html).

## It says "Waiting for GPS fix"

Go outside or to a window, and check that Location is on for your phone and that you allowed FindCache to use it ("While using the app", precise). The first fix can take a minute.

## The compass arrow points the wrong way

Hold the phone **flat**, away from magnets, speaker cases and metal. If Android asks for calibration, wave the phone in a figure-8. If the ring seems off, the arrow also needs a good fix: check the GPS accuracy under the compass.

## What does the uncertainty radius mean?

It is the honest "about this close" circle. It combines how accurate your fix is now with how accurate the place was when it was saved, so a place saved with a rough position gets a bigger search circle. When you are inside it, look around. More in [Finding a place](findcache-finding-a-place.html).

## A friend's phone does not appear when I share

Both phones need Bluetooth on, FindCache open on the **Share nearby** screen, and the **Nearby devices** permission allowed. Stand within a few metres, and have your friend tap **Share N places** before you tap **Look for nearby FindCache users**. See [Sharing places](findcache-sharing.html).

## Can I use FindCache without a signal?

Yes. The compass, distance and uncertainty need only GPS. Maps need a connection unless you saved the area first: see [Maps and offline use](findcache-maps.html).

## Is satellite imagery available outside the United States?

No. Satellite comes from the U.S. Geological Survey and covers the United States only. Elsewhere, use the street map.

## What does FindCache know about me?

Nothing leaves your phone unless you share or export. There is no account, advertising or analytics. Map pictures are downloaded from OpenFreeMap and the U.S. Geological Survey, which can see your network address and the area you are viewing. Read the [FindCache privacy policy](findcache-privacy.html).

## Which Android versions are supported?

Android 7 or later. High-accuracy GPS needs Android 12 or later; everything else works on older versions. Bluetooth sharing works across versions.

## I found a bug, or I have an idea

Please [get in touch](contact.html), or open an issue at the [FindCache page on GitHub](https://github.com/gwlester/FindIt). FindCache is free and open source (BSD 2-Clause).
