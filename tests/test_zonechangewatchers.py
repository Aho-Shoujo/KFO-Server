from .test_zonebasic import _TestZone

class TestZoneChangeWatchers_01_Watch(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_watch incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_watch 1000')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_watch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_newwatcher(self):
        """
        Situation: C1 creates a zone from areas 4 through 6. C2 decides to watch it.
        """

        self.c1.ooc('/zone 4, 6') # Creates zone z0
        self.c1.discard_all()
        self.assertEquals(1, len(self.zm.zones))
        self.assertEquals({self.c1}, self.zm.get_zone('z0').watchers)

        self.c2.ooc('/zone_watch {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} is now watching your zone.'.format(self.c2.name), over=True)
        self.c2.assert_ooc('You are now watching zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(1, len(self.zm.zones))
        self.assertEquals({self.c1, self.c2}, self.zm.get_zone('z0').watchers)

    def test_03_anothernewwatcher(self):
        """
        Situation: C5 too decides to watch zone z0.
        """

        self.c5.ooc('/zone_watch {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} is now watching your zone.'.format(self.c5.name), over=True)
        self.c2.assert_ooc('(X) {} is now watching your zone.'.format(self.c5.name), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You are now watching zone `{}`.'.format('z0'), over=True)
        self.assertEquals(1, len(self.zm.zones))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').watchers)

    def test_04_differentzonedifferentwatchers(self):
        """
        Situation: C0 (who is made mod) creates a zone z1. C4 (who is made mod) watches their zone.
        """

        self.c0.make_mod()
        self.c4.make_mod()
        self.c0.ooc('/zone {}, {}'.format(1, 3))
        self.c0.discard_all()

        self.c4.ooc('/zone_watch {}'.format('z1'))
        self.c0.assert_ooc('(X) {} is now watching your zone.'.format(self.c4.name), over=True)
        self.c1.assert_no_packets() # In other zone
        self.c2.assert_no_packets() # In other zone
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You are now watching zone `{}`.'.format('z1'), over=True)
        self.c5.assert_no_packets() # In other zone
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c0, self.c4}, self.zm.get_zone('z1').watchers)

    def test_05_nodoublewatching(self):
        """
        Situation: C0 attempts to watch zone z0. C1 attempts to watch z1. Both of them attempt this
        while still watching their original zones. They both fail.
        """

        self.c0.ooc('/zone_watch {}'.format('z0'))
        self.c0.assert_ooc('You cannot watch a zone while watching another.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c0, self.c4}, self.zm.get_zone('z1').watchers)

        self.c1.ooc('/zone_watch {}'.format('z1'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You cannot watch a zone while watching another.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c0, self.c4}, self.zm.get_zone('z1').watchers)

class TestZoneChangeWatchers_02_Unwatch(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_unwatch incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_unwatch')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Parameters
        self.c1.ooc('/zone_unwatch 1000')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has no arguments.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_unwatch(self):
        """
        Situation: C1 creates a zone, C2 and C5 start watching it. C2 then unwatches it.
        """

        self.c1.ooc('/zone 4, 6') # Creates zone z0
        self.c2.ooc('/zone_watch {}'.format('z0'))
        self.c5.ooc('/zone_watch {}'.format('z0'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()
        self.assertEquals({self.c1, self.c2, self.c5}, self.zm.get_zone('z0').watchers)

        self.c2.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} is no longer watching your zone.'.format(self.c2.name),
                           over=True)
        self.c2.assert_ooc('You are no longer watching zone `{}`.'.format('z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} is no longer watching your zone.'.format(self.c2.name),
                           over=True)
        self.assertEquals(1, len(self.zm.zones))
        self.assertEquals({self.c1, self.c5}, self.zm.get_zone('z0').watchers)

    def test_03_unwatchercancreate(self):
        """
        Situation: C2, who just unwatched a zone, can now freely create a zone.
        """

        self.c2.ooc('/zone 0')
        self.c2.discard_all()
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c1, self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c2}, self.zm.get_zone('z1').watchers)

    def test_04_creatorunwatches(self):
        """
        Situation: C1, the original creator of the zone, unwatches it. As someone is still watching
        it (C5), the zone survives.
        """

        self.c1.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You are no longer watching zone `{}`.'.format('z0'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} is no longer watching your zone.'.format(self.c1.name),
                           over=True)
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c2}, self.zm.get_zone('z1').watchers)

    def test_05_unwatchercanwatchothers(self):
        """
        Situation: C1, who just unwatched a zone, can now freely watch another zone.
        """

        self.c1.ooc('/zone_watch {}'.format('z1'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z1').watchers)

    def test_06_unwatchthenwatch(self):
        """
        Situation: C1 unwatches their watched zone, and can rewatch it in the future again.
        """

        self.c1.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You are no longer watching zone `{}`.'.format('z1'), over=True)
        self.c2.assert_ooc('(X) {} is no longer watching your zone.'.format(self.c1.name),
                           over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c2}, self.zm.get_zone('z1').watchers)

        self.c1.ooc('/zone_watch {}'.format('z1'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c5}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z1').watchers)

    def test_07_lastpersonunwatches(self):
        """
        Situation: C5 unwatches their zone. As they were the last person watching it, they get a
        special message about their zone being removed.
        """

        self.c5.ooc('/zone_unwatch')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You are no longer watching zone `{}`.'.format('z0'))
        self.c5.assert_ooc('As you were the last person watching it, your last zone was removed.',
                           over=True)

class TestZoneChangeWatchers_03_Disconnections(_TestZone):
    def test_01_disconnectionmorethanonewatcherremains(self):
        """
        Situation: C1 creates a zone, C2 and C5 watch it. C5 then "disconnects". Server survives as
        normal.
        """

        self.c1.ooc('/zone 4, 6') # Creates zone z0
        self.c2.ooc('/zone_watch {}'.format('z0'))
        self.c5.ooc('/zone_watch {}'.format('z0'))
        self.c1.discard_all()
        self.c2.discard_all()
        self.c5.discard_all()

        self.c5.disconnect()
        self.assertEquals(1, len(self.zm.zones))
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z0').watchers)

    def test_02_afterdccancreatemorezones(self):
        """
        Situation: C4 (who is made mod) creates a zone after a player disconnected.
        """

        self.c4.make_mod()

        self.c4.ooc('/zone 3')
        self.c4.discard_all()
        self.assertEquals(2, len(self.zm.zones))
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z0').watchers)
        self.assertEquals({self.c4}, self.zm.get_zone('z1').watchers)

    def test_03_solewatcherdcs(self):
        """
        Situation: C4, the sole watcher of zone z1, disconnects. Zone 1 thus disappears.
        """

        self.c4.disconnect()
        self.assertEquals(1, len(self.zm.zones))
        self.assertEquals({self.c2, self.c1}, self.zm.get_zone('z0').watchers)