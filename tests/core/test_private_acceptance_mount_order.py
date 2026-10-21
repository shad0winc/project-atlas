"""Runtime acceptance preserves mount identity across inspection ordering."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from atlas.deployment_private_acceptance import PrivateHeldAcceptance
from atlas.maintenance_control import MaintenanceControlError
class PrivateAcceptanceMountOrderTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.record=Path(self.temp.name)
  self.image='sha256:'+'a'*64
  (self.record/'images.tsv').write_text('ingress|compose.yml|fixture|api|/atlas-api|fixture:tag|'+self.image+'\n')
  self.collector=object.__new__(PrivateHeldAcceptance)
  self.row={'Id':'b'*64,'Name':'/atlas-api','Image':self.image,'RestartCount':0,'Config':{'Env':['A=1','B=2'],'User':'999'},'HostConfig':{'ReadonlyRootfs':True},'Mounts':[{'Type':'bind','Source':'/one','Destination':'/first','RW':False,'Mode':'ro','Propagation':'rprivate'},{'Type':'bind','Source':'/two','Destination':'/second','RW':True,'Mode':'rw','Propagation':'rprivate'}],'State':{'Running':True,'Paused':False,'Restarting':False,'OOMKilled':False,'Pid':123,'StartedAt':'fixture-start','Health':{'Status':'healthy'}}}
 def snapshot(self,row=None):
  with patch.object(self.collector,'_command',return_value=json.dumps([row or self.row]).encode()):return self.collector._runtime(self.record)
 def change_mount(self,key,value):
  changed=copy.deepcopy(self.row);changed['Mounts'][0][key]=value
  self.assertNotEqual(self.snapshot(),self.snapshot(changed))
 def test_mount_permutation_preserves_runtime_identity(self):
  changed=copy.deepcopy(self.row);changed['Mounts'].reverse();self.assertEqual(self.snapshot(),self.snapshot(changed))
 def test_source_change_detected(self):self.change_mount('Source','/changed')
 def test_destination_change_detected(self):self.change_mount('Destination','/changed')
 def test_writable_change_detected(self):self.change_mount('RW',True)
 def test_mode_change_detected(self):self.change_mount('Mode','rw')
 def test_propagation_change_detected(self):self.change_mount('Propagation','rshared')
 def test_type_change_detected(self):self.change_mount('Type','volume')
 def test_additional_metadata_change_detected(self):self.change_mount('UnreviewedMetadata',{'flag':True})
 def test_mount_addition_and_removal_detected(self):
  for mounts in (self.row['Mounts'][:1],self.row['Mounts']+[copy.deepcopy(self.row['Mounts'][0])]):
   changed=copy.deepcopy(self.row);changed['Mounts']=mounts;self.assertNotEqual(self.snapshot(),self.snapshot(changed))
 def test_configuration_list_order_is_not_normalized(self):
  changed=copy.deepcopy(self.row);changed['Config']['Env'].reverse();self.assertNotEqual(self.snapshot(),self.snapshot(changed))
 def test_process_and_restart_drift_detected(self):
  for key,value in (('Pid',456),('StartedAt','later')):
   changed=copy.deepcopy(self.row);changed['State'][key]=value;self.assertNotEqual(self.snapshot(),self.snapshot(changed))
  changed=copy.deepcopy(self.row);changed['RestartCount']=1;self.assertNotEqual(self.snapshot(),self.snapshot(changed))
 def test_container_and_host_configuration_drift_detected(self):
  changed=copy.deepcopy(self.row);changed['Id']='c'*64;self.assertNotEqual(self.snapshot(),self.snapshot(changed))
  changed=copy.deepcopy(self.row);changed['HostConfig']['ReadonlyRootfs']=False;self.assertNotEqual(self.snapshot(),self.snapshot(changed))
 def test_unhealthy_and_nonrunning_states_refused(self):
  for update in ({'Health':{'Status':'unhealthy'}},{'Running':False},{'Paused':True},{'Restarting':True},{'OOMKilled':True},{'Pid':0}):
   changed=copy.deepcopy(self.row);changed['State'].update(update)
   with self.assertRaises(MaintenanceControlError):self.snapshot(changed)
 def test_unexpected_image_refused(self):
  changed=copy.deepcopy(self.row);changed['Image']='sha256:'+'d'*64
  with self.assertRaises(MaintenanceControlError):self.snapshot(changed)
if __name__=='__main__':unittest.main()
