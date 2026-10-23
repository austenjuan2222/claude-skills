import hashlib, importlib.util, json, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('updater',Path(__file__).with_name('skill_updater.py'))
u=importlib.util.module_from_spec(spec); spec.loader.exec_module(u)

class UpdaterTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
  self.home=Path(self.temp.name); self.local=self.home/'local'; self.repo=self.home/'repo'; self.local.mkdir(); (self.repo/'skills').mkdir(parents=True)
  self.config={'skills':str(self.local),'repository':str(self.repo),'npm':'npm','sources':[]}
 def put(self,root,relative,data):
  file=root/relative; file.parent.mkdir(parents=True,exist_ok=True); file.write_bytes(data); return file
 def report(self,path='demo/SKILL.md'):
  before=b'---\nname: demo\n---\nold\n'; after=before.replace(b'old',b'new')
  self.put(self.local,path,before); self.put(self.repo/'skills',path,before)
  folder=self.home/'report'; self.put(folder/'candidate',path,after)
  obj={'local_root':str(self.local.resolve()),'errors':[],'changes':[{'path':path,'kind':'modify','before_sha256':u.digest(before),'after_sha256':u.digest(after)}],'sources':[]}
  file=folder/'report.json'; u.write_json(file,obj)
  return file,u.digest(file.read_bytes()),before
 def test_paths_cannot_escape(self):
  for relative in ['../bad','/absolute','C:/Windows/bad','x/../../bad','a/C:/bad']:
   with self.assertRaises(ValueError): u.contained(self.local,relative)
 def test_backup_restores_old_and_removes_new(self):
  self.put(self.local,'demo/a',b'old'); archive=self.home/'backup.zip'
  u.backup_files([(self.local,'demo/a'),(self.local,'demo/new')],archive)
  self.put(self.local,'demo/a',b'changed'); self.put(self.local,'demo/new',b'new')
  u.restore_backup(archive,[self.local])
  self.assertEqual((self.local/'demo/a').read_bytes(),b'old'); self.assertFalse((self.local/'demo/new').exists())
 def test_foreign_backup_root_is_rejected(self):
  archive=self.home/'bad.zip'
  with zipfile.ZipFile(archive,'w') as z: z.writestr('backup.json',json.dumps([{'root':str(self.home/'outside'),'path':'a','exists':False}]))
  with self.assertRaises(ValueError): u.restore_backup(archive,[self.local])
 def test_approval_is_exact_and_required(self):
  file,approval,before=self.report()
  with self.assertRaises(ValueError): u.apply(self.config,self.home,file,'wrong')
  self.assertEqual((self.local/'demo/SKILL.md').read_bytes(),before)
 def test_local_drift_blocks_apply(self):
  file,approval,before=self.report(); self.put(self.local,'demo/SKILL.md',b'user change')
  with patch.object(u,'run',return_value=''):
   with self.assertRaisesRegex(ValueError,'changed since review'): u.apply(self.config,self.home,file,approval)
  self.assertEqual((self.local/'demo/SKILL.md').read_bytes(),b'user change')
 def test_candidate_tampering_blocks_apply(self):
  file,approval,before=self.report(); self.put(file.parent/'candidate','demo/SKILL.md',b'tampered')
  with patch.object(u,'run',return_value=''):
   with self.assertRaisesRegex(ValueError,'Candidate'): u.apply(self.config,self.home,file,approval)
  self.assertEqual((self.local/'demo/SKILL.md').read_bytes(),before)
 def test_failed_validation_rolls_back_both_copies(self):
  file,approval,before=self.report()
  self.put(self.local,'other/SKILL.md',b'---\nname: demo\n---\n')
  with patch.object(u,'run',return_value=''):
   with self.assertRaisesRegex(ValueError,'Duplicate'): u.apply(self.config,self.home,file,approval)
  self.assertEqual((self.local/'demo/SKILL.md').read_bytes(),before)
  self.assertEqual((self.repo/'skills/demo/SKILL.md').read_bytes(),before)
  self.assertEqual(u.read_json(self.home/'last-apply.json')['status'],'rolled_back')
 def test_missing_upstream_is_not_treated_as_deletion(self):
  source={'repo':'owner/repo','mappings':[{'path':'skills/demo','name':'demo'}]}
  with patch.object(u,'request',side_effect=[{'sha':'abc'},{'tree':[]}]):
   with self.assertRaisesRegex(ValueError,'missing or moved'): u.source_plan(source,self.local,self.home/'candidate',['demo/SKILL.md'])
 def test_name_and_dependency_patches_survive(self):
  data=u.patch_bytes('AThevon/genjutsu','skills/_jutsu/ui-ux-pro-max/SKILL.md',b'---\nname: ui-ux-pro-max\n---\n','abc')
  self.assertIn(b'name: genjutsu-ui-ux-pro-max',data)
  data=u.patch_bytes('zanwei/design-dna','scripts/package.json',b'{"dependencies":{"sharp":"^0.33.5"}}','abc')
  self.assertEqual(json.loads(data)['dependencies']['sharp'],'0.35.5')
 def test_nested_upstream_doc_links_resolve_from_original_path(self):
  data=u.patch_bytes('morluto/rea','.agents/skills/rea-analysis-optimization/references/kuna-case-study.md',b'[source](../../../../src/kuna/test.ts)','abc')
  self.assertEqual(data,b'[source](https://github.com/morluto/rea/blob/abc/src/kuna/test.ts)')
 def test_check_never_changes_installed_files(self):
  before=b'---\nname: demo\n---\nold'; after=before.replace(b'old',b'new')
  self.put(self.local,'demo/SKILL.md',before)
  self.config['sources']=[{'repo':'owner/repo','mappings':[{'path':'skills/demo','name':'demo'}]}]
  def fake(url,binary=False):
   if '/commits/' in url: return {'sha':'abc'}
   if '/git/trees/' in url: return {'tree':[{'path':'skills/demo/SKILL.md','type':'blob','mode':'100644','sha':u.git_blob(after)}]}
   return after
  with patch.object(u,'request',side_effect=fake),patch.object(u,'run',side_effect=AssertionError('check must not execute tools')):
   self.assertEqual(u.check(self.config,self.home),0)
   first=u.read_json(self.home/'latest.json'); self.assertTrue(first['notify'])
   self.assertEqual(u.check(self.config,self.home),0)
   self.assertFalse(u.read_json(self.home/'latest.json')['notify'])
  self.assertEqual((self.local/'demo/SKILL.md').read_bytes(),before)
 def test_partial_network_failure_blocks_application(self):
  self.config['sources']=[{'repo':'owner/repo','mappings':[]}]
  with patch.object(u,'request',side_effect=OSError('network offline')):
   self.assertEqual(u.check(self.config,self.home),1)
  report=u.read_json(Path(u.read_json(self.home/'latest.json')['report']))
  self.assertTrue(report['errors']); self.assertEqual(report['status'],'failed')

if __name__=='__main__': unittest.main()
